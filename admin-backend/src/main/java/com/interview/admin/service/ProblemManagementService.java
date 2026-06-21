package com.interview.admin.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.admin.dto.PageResponse;
import com.interview.admin.dto.ProblemRequest;
import com.interview.admin.dto.ProblemResponse;
import com.interview.admin.model.GenerationJob;
import com.interview.admin.model.Problem;
import com.interview.admin.repository.ProblemRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class ProblemManagementService {

    private static final Logger log = LoggerFactory.getLogger(ProblemManagementService.class);

    private final ProblemRepository problemRepository;
    private final ObjectMapper objectMapper;

    public ProblemManagementService(ProblemRepository problemRepository, ObjectMapper objectMapper) {
        this.problemRepository = problemRepository;
        this.objectMapper = objectMapper;
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public PageResponse<ProblemResponse> listProblems(int page, int size) {
        return PageResponse.from(
            problemRepository.findAllByOrderByCreatedAtDesc(PageRequest.of(page, size)),
            ProblemResponse::from
        );
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public ProblemResponse getProblem(UUID id) {
        return problemRepository.findById(id)
                .map(ProblemResponse::from)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public ProblemResponse createProblem(ProblemRequest request) {
        if (problemRepository.findBySlug(request.slug()).isPresent()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Slug already exists: " + request.slug());
        }
        Problem problem = Problem.create(request.slug(), request.title(), request.description(),
                request.difficulty(), request.problemLink(), request.tags());
        return ProblemResponse.from(problemRepository.save(problem));
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public ProblemResponse updateProblem(UUID id, ProblemRequest request) {
        Problem problem = problemRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));
        problem.setSlug(request.slug());
        problem.setTitle(request.title());
        problem.setDescription(request.description());
        problem.setDifficulty(request.difficulty());
        problem.setProblemLink(request.problemLink());
        problem.setTags(request.tags());
        return ProblemResponse.from(problemRepository.save(problem));
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public void deleteProblem(UUID id) {
        if (!problemRepository.existsById(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found");
        }
        problemRepository.deleteById(id);
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public Problem createFromJob(GenerationJob job) {
        String slug = extractSlug(job.getResultJson(), job.getPrompt());
        slug = uniqueSlug(slug);

        String title = toTitleCase(slug.replace('-', ' '));
        String description = job.getPrompt();
        String domain = extractDomain(job.getDesignJson());
        List<String> tags = buildTags(domain, job.getLanguages());
        String problemLink = "/challenges/" + slug;

        Problem problem = Problem.create(slug, title, description, "MIXED", problemLink, tags);
        return problemRepository.save(problem);
    }

    private String extractSlug(String resultJson, String fallbackPrompt) {
        if (resultJson != null) {
            try {
                Map<String, Object> result = objectMapper.readValue(resultJson, new TypeReference<>() {});
                Object challenge = result.get("challenge");
                if (challenge instanceof String s && !s.isBlank()) return s;
            } catch (Exception e) {
                log.warn("Could not parse resultJson for slug: {}", e.getMessage());
            }
        }
        String slug = fallbackPrompt.toLowerCase().replaceAll("[^a-z0-9]+", "-").replaceAll("^-|-$", "");
        return slug.substring(0, Math.min(50, slug.length()));
    }

    private String extractDomain(String designJson) {
        if (designJson != null) {
            try {
                Map<String, Object> design = objectMapper.readValue(designJson, new TypeReference<>() {});
                Object ch = design.get("challenge");
                if (ch instanceof Map<?, ?> chMap) {
                    Object domain = chMap.get("domain");
                    if (domain instanceof String s && !s.isBlank()) return s;
                }
            } catch (Exception ignored) {}
        }
        return null;
    }

    private List<String> buildTags(String domain, List<String> languages) {
        List<String> tags = new ArrayList<>();
        if (domain != null) tags.add(domain);
        if (languages != null) tags.addAll(languages);
        return tags;
    }

    private String uniqueSlug(String base) {
        if (problemRepository.findBySlug(base).isEmpty()) return base;
        int i = 2;
        while (problemRepository.findBySlug(base + "-" + i).isPresent()) i++;
        return base + "-" + i;
    }

    private String toTitleCase(String input) {
        if (input == null || input.isBlank()) return input;
        String[] words = input.trim().split("\\s+");
        StringBuilder sb = new StringBuilder();
        for (String w : words) {
            if (!w.isEmpty()) {
                sb.append(Character.toUpperCase(w.charAt(0)));
                sb.append(w.substring(1).toLowerCase());
                sb.append(' ');
            }
        }
        return sb.toString().trim();
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public ProblemResponse setPublished(UUID id, boolean published) {
        Problem problem = problemRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));
        problem.setPublished(published);
        return ProblemResponse.from(problemRepository.save(problem));
    }
}
