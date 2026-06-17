package com.interview.platform.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.Map;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class GradingJob {
    private UUID submissionId;
    private String challengeId;
    private String language;
    private Map<String, String> files;
    
    // AI Evaluation fields
    private boolean isPremium;
    private Integer remainingTimeSeconds;
    private String userType; // "B2C" or "B2B"
}
