package com.interview.mainservice.service;

import com.interview.mainservice.dto.RunRequest;
import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.model.Problem;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class RunService {

    private static final String DEFAULT_LANGUAGE = "java";

    private final ProblemService problemService;
    private final ExecutionService executionService;

    public RunService(ProblemService problemService, ExecutionService executionService) {
        this.problemService = problemService;
        this.executionService = executionService;
    }

    public RunResponse run(UUID userId, UUID problemId, RunRequest request) {
        Problem problem = problemService.findProblemEntity(problemId);
        validateForExecution(problem);

        String language = problem.getLanguage() != null ? problem.getLanguage() : DEFAULT_LANGUAGE;
        String sessionId = SessionIdentifier.of(userId, problemId);
        return executionService.execute(sessionId, problem.getEcrImageUri(), language, request.files(),
                ExecutionService.resolveCommand(language));
    }

    public void openSession(UUID userId, UUID problemId) {
        Problem problem = problemService.findProblemEntity(problemId);
        validateForExecution(problem);

        String sessionId = SessionIdentifier.of(userId, problemId);
        executionService.warmUp(sessionId, problem.getEcrImageUri());
    }

    private void validateForExecution(Problem problem) {
        if (problem.getEcrImageUri() == null) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Problem has no execution image configured");
        }
    }
}
