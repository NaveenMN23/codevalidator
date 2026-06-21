package com.interview.mainservice.service;

import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.dto.SubmitRequest;
import com.interview.mainservice.model.Problem;
import com.interview.mainservice.repository.ProblemRepository;
import io.github.resilience4j.bulkhead.BulkheadFullException;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class SubmitService {

    // Same command as Run — both just run `mvn test`; the difference is Submit has the hidden
    // test injected first. Matches the existing "one-at-a-time" failure feedback the platform
    // already uses for grading.
    private static final String LANGUAGE = "java";
    private static final String SUBMIT_COMMAND = "mvn -o test -Dsurefire.skipAfterFailureCount=1";

    private final ProblemRepository problemRepository;
    private final ExecutionServiceClient executionServiceClient;

    public SubmitService(ProblemRepository problemRepository, ExecutionServiceClient executionServiceClient) {
        this.problemRepository = problemRepository;
        this.executionServiceClient = executionServiceClient;
    }

    public RunResponse submit(UUID userId, UUID problemId, SubmitRequest request) {
        Problem problem = problemRepository.findById(problemId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));

        String tier = problem.getTier();
        if (tier == null || tier.isBlank()) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "Problem has no tier configured — cannot locate its hidden test");
        }

        // Same session id as Run — reuses the session's warm container rather than a fresh one.
        String sessionId = SessionIdentifier.of(userId, problemId);
        try {
            return executionServiceClient.submit(sessionId, problem.getSlug(), tier, LANGUAGE,
                    request.files(), SUBMIT_COMMAND);
        } catch (BulkheadFullException e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "Execution Service is at capacity, try again shortly");
        }
    }
}
