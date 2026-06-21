package com.interview.admin.dto;

import com.interview.admin.model.GenerationJob;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record GenerationJobResponse(
    UUID id,
    String status,
    String prompt,
    List<String> languages,
    List<String> tiers,
    int scenariosPerTier,
    String designJson,
    String resultJson,
    String error,
    UUID problemId,
    Instant createdAt,
    Instant updatedAt
) {
    public static GenerationJobResponse from(GenerationJob job) {
        return new GenerationJobResponse(
            job.getId(),
            job.getStatus().name(),
            job.getPrompt(),
            job.getLanguages(),
            job.getTiers(),
            job.getScenariosPerTier(),
            job.getDesignJson(),
            job.getResultJson(),
            job.getError(),
            job.getProblemId(),
            job.getCreatedAt(),
            job.getUpdatedAt()
        );
    }
}
