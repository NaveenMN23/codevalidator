package com.interview.mainservice.service;

import com.interview.mainservice.dto.RunRequest;
import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.model.Problem;
import com.interview.mainservice.repository.ProblemRepository;
import io.github.resilience4j.bulkhead.BulkheadFullException;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class RunService {

    // v1 is Java-first per docs/design/deferred-eager-final-architecture.md; Problem has no
    // language column yet — generalize this once Node/Python challenges are added.
    private static final String LANGUAGE = "java";
    private static final String RUN_COMMAND = "mvn -o test -Dsurefire.skipAfterFailureCount=1";

    private final ProblemRepository problemRepository;
    private final ExecutionServiceClient executionServiceClient;

    public RunService(ProblemRepository problemRepository, ExecutionServiceClient executionServiceClient) {
        this.problemRepository = problemRepository;
        this.executionServiceClient = executionServiceClient;
    }

    public RunResponse run(UUID userId, UUID problemId, RunRequest request) {
        Problem problem = problemRepository.findById(problemId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));

        String sessionId = SessionIdentifier.of(userId, problemId);
        try {
            return executionServiceClient.execute(sessionId, problem.getSlug(), LANGUAGE,
                    request.files(), RUN_COMMAND);
        } catch (BulkheadFullException e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "Execution Service is at capacity, try again shortly");
        }
    }
}
