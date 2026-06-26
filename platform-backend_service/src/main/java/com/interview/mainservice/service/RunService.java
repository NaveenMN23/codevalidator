package com.interview.mainservice.service;

import com.interview.mainservice.dto.RunRequest;
import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.model.Problem;
import com.interview.mainservice.repository.ProblemRepository;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class RunService {

    private static final String DEFAULT_LANGUAGE = "java";
    private static final String RUN_COMMAND = "mvn -o test -Dsurefire.skipAfterFailureCount=1";

    private final ProblemRepository problemRepository;
    private final ExecutionService executionService;

    public RunService(ProblemRepository problemRepository, ExecutionService executionService) {
        this.problemRepository = problemRepository;
        this.executionService = executionService;
    }

    public RunResponse run(UUID userId, UUID problemId, RunRequest request) {
        Problem problem = problemRepository.findById(problemId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));

        if (problem.getEcrImageUri() == null) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Problem has no execution image configured");
        }

        String sessionId = SessionIdentifier.of(userId, problemId);
        return executionService.execute(sessionId, problem.getEcrImageUri(), request.files(), RUN_COMMAND);
    }
}
