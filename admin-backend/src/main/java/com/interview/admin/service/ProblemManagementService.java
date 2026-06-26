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
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProblemManagementService {

    private static final Logger log = LoggerFactory.getLogger(ProblemManagementService.class);

    private final ProblemRepository problemRepository;
    private final ObjectMapper objectMapper;
    private final DockerImageService dockerImageService;

    public ProblemManagementService(ProblemRepository problemRepository, ObjectMapper objectMapper, DockerImageService dockerImageService) {
        this.problemRepository = problemRepository;
        this.objectMapper = objectMapper;
        this.dockerImageService = dockerImageService;
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

    @Transactional
    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public List<Problem> createFromJob(GenerationJob job) {
        String challengeSlug = extractSlug(job.getResultJson(), job.getPrompt());
        String description = job.getPrompt();
        String domain = extractDomain(job.getDesignJson());
        List<String> tiers = job.getTiers();
        List<String> tags = buildTags(domain, job.getLanguages());
        String language = (job.getLanguages() != null && !job.getLanguages().isEmpty())
                ? job.getLanguages().get(0) : "node";

        Map<String, String> blueprintsBySlug = extractBlueprints(job.getResultJson());

        List<Map<String, Object>> scenarios = extractAllScenarios(job.getResultJson(), language);
        if (scenarios.isEmpty()) {
            String slug = uniqueSlug(challengeSlug);
            String difficulty = (tiers != null && !tiers.isEmpty()) ? tiers.get(0).toUpperCase() : "EASY";
            // S3 key format: {language}/{challengeSlug}.zip — must match what StorageClient uploads
            String problemLink = language.toLowerCase() + "/" + challengeSlug + ".zip";
            Problem p = Problem.create(slug, toTitleCase(slug.replace('-', ' ')), description, difficulty, problemLink, tags);
            p.setTiers(tiers != null ? tiers : List.of());
            p.setLanguage(language);
            p.setTier((tiers != null && !tiers.isEmpty()) ? tiers.get(0) + "-scenario-1" : "easy-scenario-1");
            p.setPublished(true);
            String bpJson = blueprintsBySlug.get(slug);
            if (bpJson != null) p.setBlueprint(bpJson);
            return List.of(problemRepository.save(p));
        }

        List<Problem> created = new ArrayList<>();
        for (Map<String, Object> scenario : scenarios) {
            String tag = (String) scenario.get("tag");
            if (tag == null || tag.isBlank()) continue;
            String tierStr = scenario.get("tier") instanceof String t ? t : "easy";
            String difficulty = tierStr.toUpperCase();
            String originalSlug = challengeSlug + "-" + tag;
            String slug = uniqueSlug(originalSlug);
            String title = toTitleCase(slug.replace('-', ' '));
            String problemLink = language.toLowerCase() + "/" + originalSlug + ".zip";
            Problem p = Problem.create(slug, title, description, difficulty, problemLink, tags);
            p.setTiers(tiers != null ? tiers : List.of());
            p.setLanguage(language);
            p.setTier(tag);
            p.setPublished(true);
            String bpJson = blueprintsBySlug.get(challengeSlug + "-" + tag);
            if (bpJson != null) p.setBlueprint(bpJson);
            created.add(problemRepository.save(p));
        }
        return created;
    }

    @SuppressWarnings("unchecked")
    private Map<String, String> extractBlueprints(String resultJson) {
        if (resultJson == null) return Map.of();
        try {
            Map<String, Object> result = objectMapper.readValue(resultJson, new TypeReference<>() {});
            Object blueprints = result.get("blueprints");
            if (!(blueprints instanceof Map<?, ?> bpMap)) return Map.of();
            Map<String, String> out = new java.util.HashMap<>();
            for (Map.Entry<?, ?> entry : bpMap.entrySet()) {
                out.put(String.valueOf(entry.getKey()), objectMapper.writeValueAsString(entry.getValue()));
            }
            return out;
        } catch (Exception e) {
            log.warn("Could not extract blueprints from resultJson: {}", e.getMessage());
            return Map.of();
        }
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> extractAllScenarios(String resultJson, String language) {
        if (resultJson == null) return List.of();
        try {
            Map<String, Object> result = objectMapper.readValue(resultJson, new TypeReference<>() {});
            Object manifests = result.get("manifests");
            if (!(manifests instanceof Map<?, ?> manifestsMap)) return List.of();
            Object langManifest = manifestsMap.get(language);
            if (!(langManifest instanceof Map<?, ?> lm)) return List.of();
            Object scenarios = lm.get("scenarios");
            if (scenarios == null) return List.of();

            // Actual codegen format: scenarios is a Map keyed by scenario name
            if (scenarios instanceof Map<?, ?> scenariosMap) {
                List<Map<String, Object>> results = new ArrayList<>();
                for (Map.Entry<?, ?> entry : scenariosMap.entrySet()) {
                    if (!(entry.getValue() instanceof Map<?, ?> sm)) continue;
                    String scenarioKey = String.valueOf(entry.getKey()); // e.g. "easy-restock-product"
                    String tier = sm.get("tier") instanceof String t ? t
                                  : (scenarioKey.contains("-") ? scenarioKey.split("-")[0] : scenarioKey);
                    Map<String, Object> info = new java.util.LinkedHashMap<>();
                    info.put("tag", scenarioKey);  // actual key — becomes slug suffix AND tier field
                    info.put("tier", tier);        // difficulty prefix ("easy", "medium", "hard")
                    results.add(info);
                }
                return results;
            }

            // Legacy array format
            if (scenarios instanceof List<?> list) {
                return list.stream()
                        .filter(s -> s instanceof Map<?, ?>)
                        .map(s -> (Map<String, Object>) s)
                        .toList();
            }
        } catch (Exception e) {
            log.warn("Could not extract scenarios from resultJson: {}", e.getMessage());
        }
        return List.of();
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

    public void buildImage(UUID id) {
        Problem problem = problemRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));
        dockerImageService.buildAndPush(problem.getSlug(), problem.getLanguage(), problem.getProblemLink());
    }
}
