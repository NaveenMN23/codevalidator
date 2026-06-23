package com.interview.mainservice.dto;

import com.interview.mainservice.model.Difficulty;
import java.util.List;
import java.util.UUID;

public record ProblemSummaryResponse(UUID id, String slug, String title, Difficulty difficulty, String language, String zipUrl, List<String> tags) {
}
