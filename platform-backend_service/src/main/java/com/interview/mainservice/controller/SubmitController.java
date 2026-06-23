package com.interview.mainservice.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.dto.SubmitRequest;
import com.interview.mainservice.messaging.GradingPublisher;
import com.interview.mainservice.model.Problem;
import com.interview.mainservice.model.Submission;
import com.interview.mainservice.repository.ProblemRepository;
import com.interview.mainservice.repository.SubmissionRepository;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/problems")
public class SubmitController {

    private static final Logger log = LoggerFactory.getLogger(SubmitController.class);

    private final ProblemRepository problemRepository;
    private final SubmissionRepository submissionRepository;
    private final GradingPublisher gradingPublisher;
    private final ObjectMapper objectMapper;
    private final ExecutorService executionServiceExecutor;

    public SubmitController(ProblemRepository problemRepository,
                             SubmissionRepository submissionRepository,
                             GradingPublisher gradingPublisher,
                             ObjectMapper objectMapper,
                             ExecutorService executionServiceExecutor) {
        this.problemRepository = problemRepository;
        this.submissionRepository = submissionRepository;
        this.gradingPublisher = gradingPublisher;
        this.objectMapper = objectMapper;
        this.executionServiceExecutor = executionServiceExecutor;
    }

    @PostMapping("/{id}/submit")
    public ResponseEntity<Map<String, String>> submit(@PathVariable("id") UUID problemId,
                                                       @AuthenticationPrincipal UUID userId,
                                                       @RequestBody SubmitRequest request) {
        Problem problem = problemRepository.findById(problemId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));

        // Create submission record with PENDING status immediately
        Submission submission = new Submission(userId, problemId, "", Instant.now());
        submission.setStatus("PENDING");
        submissionRepository.save(submission);
        UUID submissionId = submission.getId();

        // Fire-and-forget: serialize files and publish to grading queue
        executionServiceExecutor.submit(() -> {
            try {
                String filesJson = objectMapper.writeValueAsString(request.files());
                int remainingTime = request.remainingTimeSeconds() != null ? request.remainingTimeSeconds() : 3600;
                String userType = request.userType() != null ? request.userType() : "B2C";
                gradingPublisher.publishGradingRequest(submissionId, problemId, userId,
                        filesJson, remainingTime, userType);
            } catch (JsonProcessingException e) {
                log.error("Failed to serialize files for submission {}: {}", submissionId, e.getMessage());
                Submission s = submissionRepository.findById(submissionId).orElse(null);
                if (s != null) {
                    s.setStatus("FAILED");
                    submissionRepository.save(s);
                }
            }
        });

        return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of("id", submissionId.toString()));
    }
}
