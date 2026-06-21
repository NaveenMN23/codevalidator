package com.interview.admin.dto;

import com.interview.admin.model.Submission;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record SubmissionResponse(
    UUID id,
    UUID userId,
    UUID problemId,
    String submissionLink,
    BigDecimal score,
    Instant submittedAt
) {
    public static SubmissionResponse from(Submission s) {
        return new SubmissionResponse(
            s.getId(), s.getUserId(), s.getProblemId(),
            s.getSubmissionLink(), s.getScore(), s.getSubmittedAt()
        );
    }
}
