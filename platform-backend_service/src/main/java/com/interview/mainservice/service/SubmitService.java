package com.interview.mainservice.service;

import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.dto.SubmitRequest;
import com.interview.mainservice.model.Problem;
import com.interview.mainservice.repository.ProblemRepository;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class SubmitService {

    private static final String DEFAULT_LANGUAGE = "java";
    private static final String SUBMIT_COMMAND = "mvn -o test -Dsurefire.skipAfterFailureCount=1";

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

        String language = problem.getLanguage() != null ? problem.getLanguage() : DEFAULT_LANGUAGE;
        String sessionId = SessionIdentifier.of(userId, problemId);
        return executionService.submit(sessionId, problem.getEcrImageUri(),
                problem.getSlug(), language, request.files(), SUBMIT_COMMAND);
    }
}
