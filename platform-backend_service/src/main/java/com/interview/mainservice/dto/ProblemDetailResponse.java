package com.interview.mainservice.dto;

import com.interview.mainservice.model.Difficulty;
import java.util.List;
import java.util.UUID;

public record ProblemDetailResponse(
        UUID id,
        String slug,
        String title,
        String description,
        Difficulty difficulty,
        String problemLink,
        List<String> tags) {
}
