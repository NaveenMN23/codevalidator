package com.interview.mainservice.service;

import com.interview.mainservice.dto.PageResponse;
import com.interview.mainservice.dto.ProblemDetailResponse;
import com.interview.mainservice.dto.ProblemSummaryResponse;
import com.interview.mainservice.model.Problem;
import com.interview.mainservice.repository.ProblemRepository;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import java.util.Map;
import java.util.UUID;
import org.springframework.context.annotation.Lazy;
import org.springframework.dao.DataAccessException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ProblemService {

    private final ProblemRepository problemRepository;
    private final ChallengeStorageService challengeStorageService;
    // Self-injected proxy: needed so listProblems()/getProblem() calling findProblemEntity()
    // goes through the Spring AOP proxy (this.findProblemEntity(...) would bypass it,
    // silently disabling @CircuitBreaker/@Retryable).
    private final ProblemService self;

    public ProblemService(ProblemRepository problemRepository,
                           ChallengeStorageService challengeStorageService,
                           @Lazy ProblemService self) {
        this.problemRepository = problemRepository;
        this.challengeStorageService = challengeStorageService;
        this.self = self;
    }

    public PageResponse<ProblemSummaryResponse> listProblems(Pageable pageable) {
        return PageResponse.from(self.findPublishedProblems(pageable).map(this::toSummary));
    }

    // Metadata only — deliberately does not touch S3. Callers that already have a local
    // draft (see Workspace.tsx) skip getProblemFiles() entirely and never pay the S3 cost.
    public ProblemDetailResponse getProblem(UUID id) {
        Problem problem = self.findProblemEntity(id);
        return new ProblemDetailResponse(problem.getId(), problem.getSlug(), problem.getTitle(),
                problem.getDescription(), problem.getDifficulty(), problem.getLanguage(), Map.of(),
                problem.getProblemLink(), problem.getTags());
    }

    public Map<String, String> getProblemFiles(UUID id) {
        Problem problem = self.findProblemEntity(id);
        // MinIO key format: {language}/{slug}.zip (e.g. python/calculator-application-easy-perform-operations.zip)
        String language = problem.getLanguage() != null ? problem.getLanguage().toLowerCase() : "python";
        String s3Key = language + "/" + problem.getSlug() + ".zip";
        return challengeStorageService.fetchFiles(problem.getId(), s3Key);
    }

    @CircuitBreaker(name = "database")
    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public Page<Problem> findPublishedProblems(Pageable pageable) {
        return problemRepository.findByIsPublishedTrue(pageable);
    }

    @CircuitBreaker(name = "database")
    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public Problem findProblemEntity(UUID id) {
        return problemRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));
    }

    private ProblemSummaryResponse toSummary(Problem problem) {
        return new ProblemSummaryResponse(problem.getId(), problem.getSlug(), problem.getTitle(),
                problem.getDifficulty(), problem.getLanguage(), problem.getTags());
    }
}
