package com.interview.mainservice.dto;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record SubmissionDetailResponse(UUID id, String status, Double score, String logs,
                                        Instant submittedAt, Map<String, String> files) {
}
