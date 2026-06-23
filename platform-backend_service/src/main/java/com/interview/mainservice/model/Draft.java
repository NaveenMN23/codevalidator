package com.interview.mainservice.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.IdClass;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "drafts")
@IdClass(DraftId.class)
public class Draft {

    @Id
    @Column(name = "user_id")
    private UUID userId;

    @Id
    @Column(name = "problem_id")
    private UUID problemId;

    @Column(name = "draft_link", nullable = false)
    private String draftLink;

    @Column(name = "files_json", columnDefinition = "TEXT")
    private String filesJson;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected Draft() {
    }

    public Draft(UUID userId, UUID problemId, String draftLink) {
        this.userId = userId;
        this.problemId = problemId;
        this.draftLink = draftLink;
    }

    @PrePersist
    @PreUpdate
    void touch() {
        updatedAt = Instant.now();
    }

    public UUID getUserId() {
        return userId;
    }

    public UUID getProblemId() {
        return problemId;
    }

    public String getDraftLink() {
        return draftLink;
    }

    public String getFilesJson() {
        return filesJson;
    }

    public void setFilesJson(String filesJson) {
        this.filesJson = filesJson;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
