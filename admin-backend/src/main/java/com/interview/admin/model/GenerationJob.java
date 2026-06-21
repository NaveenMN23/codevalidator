package com.interview.admin.model;

import com.interview.admin.util.Uuidv7;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "generation_jobs")
public class GenerationJob {

    @Id
    private UUID id;

    @Column(nullable = false, columnDefinition = "text")
    private String prompt;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]", nullable = false)
    private List<String> languages;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]", nullable = false)
    private List<String> tiers;

    @Column(name = "scenarios_per_tier", nullable = false)
    private int scenariosPerTier;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private GenerationJobStatus status;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "design_json", columnDefinition = "jsonb")
    private String designJson;

    @Column(name = "design_feedback")
    private String designFeedback;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "result_json", columnDefinition = "jsonb")
    private String resultJson;

    @Column(name = "problem_id")
    private UUID problemId;

    @Column
    private String error;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected GenerationJob() {}

    public static GenerationJob create(String prompt, List<String> languages, List<String> tiers, int scenariosPerTier) {
        GenerationJob job = new GenerationJob();
        job.prompt = prompt;
        job.languages = languages;
        job.tiers = tiers;
        job.scenariosPerTier = scenariosPerTier;
        job.status = GenerationJobStatus.DESIGNING;
        return job;
    }

    @PrePersist
    void onCreate() {
        if (id == null) id = Uuidv7.generate();
        Instant now = Instant.now();
        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
    }

    public UUID getId() { return id; }
    public String getPrompt() { return prompt; }
    public List<String> getLanguages() { return languages; }
    public List<String> getTiers() { return tiers; }
    public int getScenariosPerTier() { return scenariosPerTier; }
    public GenerationJobStatus getStatus() { return status; }
    public String getDesignJson() { return designJson; }
    public String getDesignFeedback() { return designFeedback; }
    public String getResultJson() { return resultJson; }
    public UUID getProblemId() { return problemId; }
    public String getError() { return error; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }

    public void setStatus(GenerationJobStatus status) { this.status = status; }
    public void setDesignJson(String designJson) { this.designJson = designJson; }
    public void setDesignFeedback(String designFeedback) { this.designFeedback = designFeedback; }
    public void setResultJson(String resultJson) { this.resultJson = resultJson; }
    public void setProblemId(UUID problemId) { this.problemId = problemId; }
    public void setError(String error) { this.error = error; }
}
