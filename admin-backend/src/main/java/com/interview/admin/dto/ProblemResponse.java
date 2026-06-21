package com.interview.admin.dto;

import com.interview.admin.model.Problem;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record ProblemResponse(
    UUID id,
    String slug,
    String title,
    String description,
    String difficulty,
    String problemLink,
    List<String> tags,
    boolean isPublished,
    Instant createdAt,
    Instant updatedAt
) {
    public static ProblemResponse from(Problem p) {
        return new ProblemResponse(
            p.getId(), p.getSlug(), p.getTitle(), p.getDescription(),
            p.getDifficulty(), p.getProblemLink(), p.getTags(),
            p.isPublished(), p.getCreatedAt(), p.getUpdatedAt()
        );
    }
}
