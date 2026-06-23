package com.interview.mainservice.dto;

import com.interview.mainservice.model.Difficulty;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ProblemDetailResponse(
        UUID id,
        String slug,
        String title,
        String description,
        Difficulty difficulty,
        String language,
        Map<String, String> files,
        String problemLink,
        List<String> tags) {
}
