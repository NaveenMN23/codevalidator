package com.interview.mainservice.service;

import com.interview.mainservice.dto.PageResponse;
import com.interview.mainservice.dto.ProblemDetailResponse;
import com.interview.mainservice.dto.ProblemSummaryResponse;
import com.interview.mainservice.model.Problem;
import com.interview.mainservice.repository.ProblemRepository;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import java.util.UUID;
import org.springframework.dao.DataAccessException;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ProblemService {

    private final ProblemRepository problemRepository;

    public ProblemService(ProblemRepository problemRepository) {
        this.problemRepository = problemRepository;
    }

    @CircuitBreaker(name = "database")
    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public PageResponse<ProblemSummaryResponse> listProblems(Pageable pageable) {
        return PageResponse.from(problemRepository.findByIsPublishedTrue(pageable).map(this::toSummary));
    }

    @CircuitBreaker(name = "database")
    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public ProblemDetailResponse getProblem(UUID id) {
        Problem problem = problemRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));
        return toDetail(problem);
    }

    private ProblemSummaryResponse toSummary(Problem problem) {
        return new ProblemSummaryResponse(problem.getId(), problem.getSlug(), problem.getTitle(),
                problem.getDifficulty(), problem.getTags());
    }

    private ProblemDetailResponse toDetail(Problem problem) {
        return new ProblemDetailResponse(problem.getId(), problem.getSlug(), problem.getTitle(),
                problem.getDescription(), problem.getDifficulty(), problem.getProblemLink(), problem.getTags());
    }
}
