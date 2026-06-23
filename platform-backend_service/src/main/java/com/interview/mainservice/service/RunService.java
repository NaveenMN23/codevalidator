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

    // v1 is Java-first per docs/design/deferred-eager-final-architecture.md — the Execution
    // Service only has a Java executor wired up so far (see SUPPORTED_LANGUAGES in
    // session_container_manager.py). Reading problem.getLanguage() instead of hardcoding it
    // here means an unsupported language fails with an honest error from the Execution
    // Service rather than being silently mislabeled as Java.
    private static final String DEFAULT_LANGUAGE = "java";
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

        String language = problem.getLanguage() != null ? problem.getLanguage() : DEFAULT_LANGUAGE;
        String sessionId = SessionIdentifier.of(userId, problemId);
        try {
            return executionServiceClient.execute(sessionId, problem.getSlug(), language,
                    request.files(), RUN_COMMAND);
        } catch (BulkheadFullException e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "Execution Service is at capacity, try again shortly");
        }
    }
}
