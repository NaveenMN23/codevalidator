package com.interview.mainservice.controller;

import com.interview.mainservice.dto.RunRequest;
import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.service.RunService;
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
public class RunController {

    private static final Logger log = LoggerFactory.getLogger(RunController.class);

    private final RunService runService;
    private final ExecutorService executionServiceExecutor;

    public RunController(RunService runService, ExecutorService executionServiceExecutor) {
        this.runService = runService;
        this.executionServiceExecutor = executionServiceExecutor;
    }

    @PostMapping("/{id}/run")
    public DeferredResult<ResponseEntity<RunResponse>> run(@PathVariable("id") UUID problemId,
                                                             @AuthenticationPrincipal UUID userId,
                                                             @RequestBody RunRequest request) {
        DeferredResult<ResponseEntity<RunResponse>> deferredResult = new DeferredResult<>();

        // Submitting to the virtual-thread executor releases this Tomcat platform thread
        // immediately; the actual blocking call to the Execution Service happens on a
        // virtual thread, which parks cheaply while waiting (see ExecutionConfig).
        executionServiceExecutor.submit(() -> {
            try {
                RunResponse response = runService.run(userId, problemId, request);
                deferredResult.setResult(ResponseEntity.ok(response));
            } catch (ResponseStatusException e) {
                deferredResult.setResult(ResponseEntity.status(e.getStatusCode())
                        .body(new RunResponse(false, "", e.getReason(), -1)));
            } catch (Exception e) {
                log.error("Run failed for problem {}: {}", problemId, e.getMessage());
                deferredResult.setResult(ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                        .body(new RunResponse(false, "", e.getMessage(), -1)));
            }
        });

        return deferredResult;
    }

    @PostMapping("/{id}/run/session")
    public ResponseEntity<Void> openSession(@PathVariable("id") UUID problemId,
                                             @AuthenticationPrincipal UUID userId) {
        runService.openSession(userId, problemId);
        return ResponseEntity.accepted().build();
    }
}
