package com.interview.mainservice.model;

import com.interview.mainservice.util.Uuidv7;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

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

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Difficulty difficulty;

    @Column(name = "problem_link", nullable = false)
    private String problemLink;

    // Which gold-master tier/scenario this problem maps to (e.g. "beginner-divide-by-zero") —
    // used by Submit to fetch the matching hidden test from the gold-masters S3 bucket.
    @Column
    private String tier;

    @Column
    private String language;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(columnDefinition = "text[]")
    private List<String> tags;

    @Column(name = "is_published", nullable = false)
    private boolean isPublished = false;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected Problem() {
    }

    public static Problem create(String slug, String title, String description, Difficulty difficulty,
                                  String problemLink, List<String> tags, String tier) {
        Problem problem = new Problem();
        problem.slug = slug;
        problem.title = title;
        problem.description = description;
        problem.difficulty = difficulty;
        problem.problemLink = problemLink;
        problem.tags = tags;
        problem.tier = tier;
        return problem;
    }

    @PrePersist
    void onCreate() {
        if (id == null) {
            id = Uuidv7.generate();
        }
        Instant now = Instant.now();
        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
    }

    public UUID getId() {
        return id;
    }

    public String getSlug() {
        return slug;
    }

    public String getTitle() {
        return title;
    }

    public String getDescription() {
        return description;
    }

    public Difficulty getDifficulty() {
        return difficulty;
    }

    public String getProblemLink() {
        return problemLink;
    }

    public String getTier() {
        return tier;
    }

    public String getLanguage() {
        return language;
    }

    public void setLanguage(String language) {
        this.language = language;
    }

    public List<String> getTags() {
        return tags;
    }

    public boolean isPublished() {
        return isPublished;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
