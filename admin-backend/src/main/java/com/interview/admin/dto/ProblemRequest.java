package com.interview.admin.dto;

import jakarta.validation.constraints.NotBlank;
import java.util.List;

public record ProblemRequest(
    @NotBlank String slug,
    @NotBlank String title,
    String description,
    @NotBlank String difficulty,
    @NotBlank String problemLink,
    List<String> tags
) {}
