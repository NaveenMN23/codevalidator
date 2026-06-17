package com.interview.platform.model;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;
import java.util.Map;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "blueprints")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Blueprint {
    @Id
    @Column(name = "challenge_id")
    private String challengeId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "blueprint_json", nullable = false)
    private Map<String, Object> blueprintJson;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
    }
}
