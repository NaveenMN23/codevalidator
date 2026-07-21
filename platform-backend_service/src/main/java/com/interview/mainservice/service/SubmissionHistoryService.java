package com.interview.mainservice.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.model.Submission;
import com.interview.mainservice.repository.SubmissionRepository;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class SubmissionHistoryService {

    private final SubmissionRepository submissionRepository;
    private final ObjectMapper objectMapper;

    public SubmissionHistoryService(SubmissionRepository submissionRepository, ObjectMapper objectMapper) {
        this.submissionRepository = submissionRepository;
        this.objectMapper = objectMapper;
    }

    public record SubmissionDetail(UUID id, String status, Double score, String logs,
                                    Instant submittedAt, Map<String, String> files) {
    }

    public List<Submission> listSubmissions(UUID userId, UUID problemId) {
        return submissionRepository.findByUserIdAndProblemIdOrderBySubmittedAtDesc(userId, problemId);
    }

    public Optional<SubmissionDetail> getSubmission(UUID userId, UUID problemId, UUID submissionId) {
        return submissionRepository.findByIdAndUserIdAndProblemId(submissionId, userId, problemId)
                .map(submission -> {
                    Map<String, String> files = Map.of();
                    if (submission.getFilesJson() != null) {
                        try {
                            files = objectMapper.readValue(
                                    submission.getFilesJson(), new TypeReference<Map<String, String>>() {});
                        } catch (JsonProcessingException e) {
                            files = Map.of();
                        }
                    }
                    return new SubmissionDetail(submission.getId(), submission.getStatus(), submission.getScore(),
                            submission.getLogs(), submission.getSubmittedAt(), files);
                });
    }
}
