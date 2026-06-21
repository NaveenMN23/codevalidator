package com.interview.admin.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

import java.util.List;

public record GenerationPreviewRequest(
    @NotBlank String prompt,
    List<String> languages,
    List<String> tiers,
    @Min(1) @Max(5) int scenariosPerTier
) {
    public GenerationPreviewRequest {
        if (languages == null || languages.isEmpty()) languages = List.of("node");
        if (tiers == null || tiers.isEmpty()) tiers = List.of("easy", "medium", "hard");
        if (scenariosPerTier == 0) scenariosPerTier = 3;
    }
}
