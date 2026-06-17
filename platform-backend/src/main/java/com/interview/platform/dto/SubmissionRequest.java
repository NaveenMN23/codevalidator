package com.interview.platform.dto;

import lombok.Data;
import java.util.Map;
import java.util.UUID;

@Data
public class SubmissionRequest {
    private UUID userId;
    private String challengeId;
    private Map<String, String> files;

    // AI Evaluation fields
    private boolean isPremium;
    private Integer remainingTimeSeconds;
    private String userType; // "B2C" or "B2B"
}
