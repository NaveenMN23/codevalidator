package com.interview.admin.model;

import com.interview.admin.util.Uuidv7;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "problems")
public class Problem {

    @Id
    private UUID id;

    @Column(nullable = false, unique = true)
    private String slug;

    @Column(nullable = false)
    private String title;

    @Column
    private String description;

    @Column(nullable = false)
    private String difficulty;

    @Column(name = "problem_link", nullable = false)
    private String problemLink;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]")
    private List<String> tags;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]")
    private List<String> tiers;

    @Column
    private String language;

    @Column
    private String tier;

    @Column(name = "is_published", nullable = false)
    private boolean isPublished = false;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private String blueprint;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected Problem() {}

    public static Problem create(String slug, String title, String description,
                                  String difficulty, String problemLink, List<String> tags) {
        Problem p = new Problem();
        p.slug = slug;
        p.title = title;
        p.description = description;
        p.difficulty = difficulty;
        p.problemLink = problemLink;
        p.tags = tags;
        return p;
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
    public String getSlug() { return slug; }
    public String getTitle() { return title; }
    public String getDescription() { return description; }
    public String getDifficulty() { return difficulty; }
    public String getProblemLink() { return problemLink; }
    public List<String> getTags() { return tags; }
    public boolean isPublished() { return isPublished; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }

    public void setSlug(String slug) { this.slug = slug; }
    public void setTitle(String title) { this.title = title; }
    public void setDescription(String description) { this.description = description; }
    public void setDifficulty(String difficulty) { this.difficulty = difficulty; }
    public void setProblemLink(String problemLink) { this.problemLink = problemLink; }
    public void setTags(List<String> tags) { this.tags = tags; }
    public List<String> getTiers() { return tiers; }
    public void setTiers(List<String> tiers) { this.tiers = tiers; }
    public void setPublished(boolean published) { this.isPublished = published; }
    public String getLanguage() { return language; }
    public void setLanguage(String language) { this.language = language; }
    public String getTier() { return tier; }
    public void setTier(String tier) { this.tier = tier; }
    public String getBlueprint() { return blueprint; }
    public void setBlueprint(String blueprint) { this.blueprint = blueprint; }
}
