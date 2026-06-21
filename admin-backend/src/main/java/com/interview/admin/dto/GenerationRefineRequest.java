package com.interview.admin.dto;

import jakarta.validation.constraints.NotBlank;

public record GenerationRefineRequest(@NotBlank String feedback) {}
