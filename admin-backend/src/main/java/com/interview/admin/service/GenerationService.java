package com.interview.admin.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.admin.dto.GenerationJobResponse;
import com.interview.admin.dto.GenerationPreviewRequest;
import com.interview.admin.messaging.CodegenRequestPublisher;
import com.interview.admin.model.GenerationJob;
import com.interview.admin.model.GenerationJobStatus;
import com.interview.admin.model.Problem;
import com.interview.admin.repository.GenerationJobRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class GenerationService {

    private static final Logger log = LoggerFactory.getLogger(GenerationService.class);

    private final GenerationJobRepository jobRepository;
    private final CodegenRequestPublisher publisher;
    private final ObjectMapper objectMapper;
    private final ProblemManagementService problemService;

    public GenerationService(GenerationJobRepository jobRepository,
                              CodegenRequestPublisher publisher,
                              ObjectMapper objectMapper,
                              ProblemManagementService problemService) {
        this.jobRepository = jobRepository;
        this.publisher = publisher;
        this.objectMapper = objectMapper;
        this.problemService = problemService;
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public GenerationJobResponse previewDesign(GenerationPreviewRequest request) {
        GenerationJob job = GenerationJob.create(
            request.prompt(), request.languages(), request.tiers(), request.scenariosPerTier()
        );
        jobRepository.save(job);
        publisher.publishDesignPreview(job);
        return GenerationJobResponse.from(job);
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public GenerationJobResponse refineDesign(UUID jobId, String feedback) {
        GenerationJob job = jobRepository.findById(jobId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Job not found"));

        if (job.getStatus() != GenerationJobStatus.AWAITING_APPROVAL) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Job must be in AWAITING_APPROVAL status to refine. Current: " + job.getStatus());
        }

        job.setDesignFeedback(feedback);
        job.setStatus(GenerationJobStatus.DESIGNING);
        jobRepository.save(job);
        publisher.publishDesignPreview(job);
        return GenerationJobResponse.from(job);
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public GenerationJobResponse approveAndGenerate(UUID jobId) {
        GenerationJob job = jobRepository.findById(jobId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Job not found"));

        if (job.getStatus() != GenerationJobStatus.AWAITING_APPROVAL) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Job must be in AWAITING_APPROVAL status to approve. Current: " + job.getStatus());
        }

        job.setStatus(GenerationJobStatus.GENERATING);
        jobRepository.save(job);
        publisher.publishFullGenerate(job);
        return GenerationJobResponse.from(job);
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public GenerationJobResponse cancelJob(UUID jobId) {
        GenerationJob job = jobRepository.findById(jobId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Job not found"));

        if (job.getStatus() == GenerationJobStatus.COMPLETED || job.getStatus() == GenerationJobStatus.FAILED) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Cannot cancel a job in terminal state: " + job.getStatus());
        }

        job.setStatus(GenerationJobStatus.CANCELLED);
        jobRepository.save(job);
        return GenerationJobResponse.from(job);
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public GenerationJobResponse getStatus(UUID jobId) {
        return jobRepository.findById(jobId)
                .map(GenerationJobResponse::from)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Job not found"));
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public List<GenerationJobResponse> getHistory() {
        return jobRepository.findAllByOrderByCreatedAtDesc()
                .stream()
                .map(GenerationJobResponse::from)
                .collect(Collectors.toList());
    }

    public void updateFromResult(UUID jobId, String type, String status, Object payload) {
        GenerationJob job = jobRepository.findById(jobId).orElse(null);
        if (job == null) return;

        // Ignore results for cancelled jobs
        if (job.getStatus() == GenerationJobStatus.CANCELLED) {
            log.info("Ignoring result for cancelled job {}", jobId);
            return;
        }

        try {
            String payloadJson = payload != null ? objectMapper.writeValueAsString(payload) : null;

            if ("DESIGN_PREVIEW".equals(type)) {
                if ("COMPLETED".equals(status)) {
                    job.setDesignJson(payloadJson);
                    job.setStatus(GenerationJobStatus.AWAITING_APPROVAL);
                } else {
                    job.setError(payloadJson);
                    job.setStatus(GenerationJobStatus.FAILED);
                }
            } else if ("FULL_GENERATE".equals(type)) {
                if ("COMPLETED".equals(status)) {
                    job.setResultJson(payloadJson);
                    job.setStatus(GenerationJobStatus.COMPLETED);
                    jobRepository.save(job);
                    try {
                        Problem problem = problemService.createFromJob(job);
                        job.setProblemId(problem.getId());
                        log.info("Created problem {} from generation job {}", problem.getId(), jobId);
                    } catch (Exception e) {
                        log.error("Failed to create problem from job {}: {}", jobId, e.getMessage(), e);
                    }
                } else {
                    job.setError(payloadJson);
                    job.setStatus(GenerationJobStatus.FAILED);
                }
            }
            jobRepository.save(job);
        } catch (JsonProcessingException e) {
            job.setError("Failed to serialize result: " + e.getMessage());
            job.setStatus(GenerationJobStatus.FAILED);
            jobRepository.save(job);
        }
    }
}
