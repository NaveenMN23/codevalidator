package com.interview.mainservice.service;

import com.interview.mainservice.dto.PageResponse;
import com.interview.mainservice.dto.ProblemDetailResponse;
import com.interview.mainservice.dto.ProblemSummaryResponse;
import com.interview.mainservice.model.Problem;
import com.interview.mainservice.repository.ProblemRepository;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataAccessException;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;

@Service
public class ProblemService {

    private static final Logger log = LoggerFactory.getLogger(ProblemService.class);

    private final ProblemRepository problemRepository;
    private final S3Client s3Client;

    @Value("${app.aws.s3.challenges-bucket}")
    private String challengesBucket;

    public ProblemService(ProblemRepository problemRepository, S3Client s3Client) {
        this.problemRepository = problemRepository;
        this.s3Client = s3Client;
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
                problem.getDifficulty(), problem.getLanguage(), problem.getTags());
    }

    private ProblemDetailResponse toDetail(Problem problem) {
        Map<String, String> files = fetchChallengeFiles(problem);
        return new ProblemDetailResponse(problem.getId(), problem.getSlug(), problem.getTitle(),
                problem.getDescription(), problem.getDifficulty(), problem.getLanguage(), files,
                problem.getProblemLink(), problem.getTags());
    }

    private Map<String, String> fetchChallengeFiles(Problem problem) {
        String s3Key = problem.getProblemLink();
        if (s3Key == null || s3Key.isBlank()) {
            return Map.of();
        }

        Map<String, String> files = new LinkedHashMap<>();
        try (InputStream stream = s3Client.getObject(
                GetObjectRequest.builder().bucket(challengesBucket).key(s3Key).build());
             ZipInputStream zip = new ZipInputStream(stream)) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (!entry.isDirectory()) {
                    files.put(entry.getName(), new String(zip.readAllBytes()));
                }
            }
        } catch (Exception e) {
            log.error("Failed to fetch challenge files for problem {} (bucket={}, key={}): {}",
                    problem.getId(), challengesBucket, s3Key, e.getMessage());
            throw new ResponseStatusException(HttpStatus.NOT_FOUND,
                    "Challenge files not available — failed to read from storage: " + e.getMessage());
        }
        return files;
    }
}
