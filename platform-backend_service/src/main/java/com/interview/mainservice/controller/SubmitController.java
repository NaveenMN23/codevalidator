package com.interview.mainservice.controller;

import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.dto.SubmitRequest;
import com.interview.mainservice.service.SubmitService;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
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

    private final SubmitService submitService;
    private final ExecutorService executionServiceExecutor;

    public SubmitController(SubmitService submitService, ExecutorService executionServiceExecutor) {
        this.submitService = submitService;
        this.executionServiceExecutor = executionServiceExecutor;
    }

    @PostMapping("/{id}/submit")
    public DeferredResult<ResponseEntity<RunResponse>> submit(@PathVariable("id") UUID problemId,
                                                                @AuthenticationPrincipal UUID userId,
                                                                @RequestBody SubmitRequest request) {
        DeferredResult<ResponseEntity<RunResponse>> deferredResult = new DeferredResult<>();

        // Same pattern as RunController — scoped virtual-thread executor, shared Bulkhead
        // inside ExecutionServiceClient (see docs/design/deferred-eager-final-architecture.md §3).
        executionServiceExecutor.submit(() -> {
            try {
                RunResponse response = submitService.submit(userId, problemId, request);
                deferredResult.setResult(ResponseEntity.ok(response));
            } catch (ResponseStatusException e) {
                deferredResult.setResult(ResponseEntity.status(e.getStatusCode()).build());
            } catch (Exception e) {
                deferredResult.setResult(ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build());
            }
        });

        return deferredResult;
    }
}
