package com.interview.mainservice.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.IdClass;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "user_problem")
@IdClass(UserProblemId.class)
public class UserProblem {

    @Id
    @Column(name = "user_id")
    private UUID userId;

    @Id
    @Column(name = "problem_id")
    private UUID problemId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ProblemStatus status = ProblemStatus.NOT_STARTED;

    @Column(name = "best_score")
    private Double bestScore;

    @Column(name = "attempt_count", nullable = false)
    private int attemptCount = 0;

    @Column(name = "last_attempted_at")
    private Instant lastAttemptedAt;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected UserProblem() {
    }

    public UserProblem(UUID userId, UUID problemId) {
        this.userId = userId;
        this.problemId = problemId;
    }

    @PrePersist
    void onCreate() {
        Instant now = Instant.now();
        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
    }

    public UUID getUserId() {
        return userId;
    }

    public UUID getProblemId() {
        return problemId;
    }

    public ProblemStatus getStatus() {
        return status;
    }

    public Double getBestScore() {
        return bestScore;
    }

    public int getAttemptCount() {
        return attemptCount;
    }

    public Instant getLastAttemptedAt() {
        return lastAttemptedAt;
    }
}
