package com.interview.platform.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GradingResult {
    private UUID submissionId;
    private String status; // "COMPLETED", "FAILED", "TIMEOUT"
    private Integer score;
    private String output;
    private String errorOutput;
    private Integer exitCode;
}
