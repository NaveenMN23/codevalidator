package com.interview.mainservice.dto;

import java.time.Instant;
import java.util.UUID;

public record SubmissionSummaryResponse(UUID id, String status, Double score, Instant submittedAt) {
}
