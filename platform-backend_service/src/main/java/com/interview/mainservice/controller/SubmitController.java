package com.interview.mainservice.controller;

import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.dto.SubmitRequest;
import com.interview.mainservice.model.Submission;
import com.interview.mainservice.repository.ProblemRepository;
import com.interview.mainservice.repository.SubmissionRepository;
import com.interview.mainservice.service.SubmitService;
import java.time.Instant;
import java.util.LinkedHashMap;
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
import org.springframework.web.context.request.async.DeferredResult;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/problems")
public class SubmitController {

    private static final Logger log = LoggerFactory.getLogger(SubmitController.class);

    private final ProblemRepository problemRepository;
    private final SubmissionRepository submissionRepository;
    private final SubmitService submitService;
    private final ExecutorService executionServiceExecutor;

    public SubmitController(ProblemRepository problemRepository,
                             SubmissionRepository submissionRepository,
                             SubmitService submitService,
                             ExecutorService executionServiceExecutor) {
        this.problemRepository = problemRepository;
        this.submissionRepository = submissionRepository;
        this.submitService = submitService;
        this.executionServiceExecutor = executionServiceExecutor;
    }

    @PostMapping("/{id}/submit")
    public DeferredResult<ResponseEntity<Map<String, Object>>> submit(@PathVariable("id") UUID problemId,
                                                                        @AuthenticationPrincipal UUID userId,
                                                                        @RequestBody SubmitRequest request) {
        problemRepository.findById(problemId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));

        DeferredResult<ResponseEntity<Map<String, Object>>> deferredResult = new DeferredResult<>();

        // Same virtual-thread executor Run uses: releases this Tomcat platform thread
        // immediately and parks cheaply on the blocking Execution Service call instead
        // (see ExecutionConfig, RunController).
        executionServiceExecutor.submit(() -> {
            try {
                RunResponse result = submitService.submit(userId, problemId, request);
                Submission submission = saveSubmission(userId, problemId, result);
                deferredResult.setResult(ResponseEntity.ok(toResponse(submission)));
            } catch (ResponseStatusException e) {
                deferredResult.setResult(ResponseEntity.status(e.getStatusCode()).build());
            } catch (Exception e) {
                log.error("Submit failed for problem {}: {}", problemId, e.getMessage());
                deferredResult.setResult(ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build());
            }
        });

        return deferredResult;
    }

    private Submission saveSubmission(UUID userId, UUID problemId, RunResponse result) {
        Submission submission = new Submission(userId, problemId, "", Instant.now());
        submission.setStatus(result.success() ? "COMPLETED" : "FAILED");
        submission.setScore(result.success() ? 100.0 : 0.0);
        submission.setLogs(result.success() ? result.stdout() : result.stdout() + "\n" + result.stderr());
        return submissionRepository.save(submission);
    }

    private Map<String, Object> toResponse(Submission submission) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("id", submission.getId().toString());
        body.put("status", submission.getStatus());
        body.put("score", submission.getScore());
        body.put("logs", submission.getLogs());
        return body;
    }
}
