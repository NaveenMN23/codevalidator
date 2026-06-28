package com.interview.mainservice.service;

import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.dto.SubmitRequest;
import com.interview.mainservice.model.Problem;
import com.interview.mainservice.repository.ProblemRepository;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class SubmitService {

    private static final String DEFAULT_LANGUAGE = "java";
    private static final Map<String, String> SUBMIT_COMMANDS = Map.of(
            "java",   "mvn -o test -Dsurefire.skipAfterFailureCount=1",
            "node",   "npm test",
            "python", "pytest"
    );

    private final ProblemRepository problemRepository;
    private final ExecutionService executionService;

    public SubmitService(ProblemRepository problemRepository, ExecutionService executionService) {
        this.problemRepository = problemRepository;
        this.executionService = executionService;
    }

    public RunResponse submit(UUID userId, UUID problemId, SubmitRequest request) {
        Problem problem = problemRepository.findById(problemId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));

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
                problem.getHiddenTestKey(), language, request.files(), resolveCommand(language));
    }

    private String resolveCommand(String language) {
        String command = SUBMIT_COMMANDS.get(language);
        if (command == null) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Unsupported language: " + language);
        }
        return command;
    }
}
