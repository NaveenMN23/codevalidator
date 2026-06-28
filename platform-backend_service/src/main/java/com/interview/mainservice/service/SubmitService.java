package com.interview.mainservice.service;

import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.dto.SubmitRequest;
import com.interview.mainservice.model.Problem;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class SubmitService {

    private static final String DEFAULT_LANGUAGE = "java";

    private final ProblemService problemService;
    private final ExecutionService executionService;

    public SubmitService(ProblemService problemService, ExecutionService executionService) {
        this.problemService = problemService;
        this.executionService = executionService;
    }

    public RunResponse submit(UUID userId, UUID problemId, SubmitRequest request) {
        Problem problem = problemService.findProblemEntity(problemId);

        if (problem.getEcrImageUri() == null) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Problem has no execution image configured");
        }

        if (problem.getHiddenTestKey() == null) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Problem has no hidden test configured");
        }

        String language = problem.getLanguage() != null ? problem.getLanguage() : DEFAULT_LANGUAGE;
        String sessionId = SessionIdentifier.of(userId, problemId);
        return executionService.submit(sessionId, problem.getEcrImageUri(),
                problem.getHiddenTestKey(), language, request.files(),
                ExecutionService.resolveCommand(language));
    }
}
