package com.interview.admin.model;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "submissions")
public class Submission {

    @Id
    private UUID id;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "problem_id", nullable = false)
    private UUID problemId;

    @Column(name = "submission_link", nullable = false)
    private String submissionLink;

    @Column
    private BigDecimal score;

    @Column(name = "submitted_at", nullable = false)
    private Instant submittedAt;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected Submission() {}

    public UUID getId() { return id; }
    public UUID getUserId() { return userId; }
    public UUID getProblemId() { return problemId; }
    public String getSubmissionLink() { return submissionLink; }
    public BigDecimal getScore() { return score; }
    public Instant getSubmittedAt() { return submittedAt; }
    public Instant getCreatedAt() { return createdAt; }
}
