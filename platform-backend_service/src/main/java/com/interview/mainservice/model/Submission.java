package com.interview.mainservice.model;

import com.interview.mainservice.util.Uuidv7;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
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

    @Column(nullable = false)
    private String status = "PENDING";

    @Column
    private Double score;

    @Column(name = "feedback_json", columnDefinition = "TEXT")
    private String feedbackJson;

    @Column(name = "submitted_at", nullable = false)
    private Instant submittedAt;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected Submission() {
    }

    public Submission(UUID userId, UUID problemId, String submissionLink, Instant submittedAt) {
        this.userId = userId;
        this.problemId = problemId;
        this.submissionLink = submissionLink;
        this.submittedAt = submittedAt;
    }

    @PrePersist
    void onCreate() {
        if (id == null) {
            id = Uuidv7.generate();
        }
        createdAt = Instant.now();
    }

    public UUID getId() {
        return id;
    }

    public UUID getUserId() {
        return userId;
    }

    public UUID getProblemId() {
        return problemId;
    }

    public String getSubmissionLink() {
        return submissionLink;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Double getScore() {
        return score;
    }

    public void setScore(Double score) {
        this.score = score;
    }

    public String getFeedbackJson() {
        return feedbackJson;
    }

    public void setFeedbackJson(String feedbackJson) {
        this.feedbackJson = feedbackJson;
    }

    public Instant getSubmittedAt() {
        return submittedAt;
    }
}
