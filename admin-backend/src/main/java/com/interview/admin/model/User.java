package com.interview.admin.model;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "users")
public class User {

    @Id
    private UUID id;

    @Column(nullable = false, unique = true)
    private String email;

    @Column(name = "password_hash")
    private String passwordHash;

    @Column(name = "auth_provider")
    private String authProvider;

    @Column(name = "display_name")
    private String displayName;

    @Column(name = "is_admin", nullable = false)
    private boolean isAdmin = false;

    @Column(name = "created_at")
    private Instant createdAt;

    @Column(name = "updated_at")
    private Instant updatedAt;

    protected User() {}

    public UUID getId() { return id; }
    public String getEmail() { return email; }
    public String getPasswordHash() { return passwordHash; }
    public String getAuthProvider() { return authProvider; }
    public String getDisplayName() { return displayName; }
    public boolean isAdmin() { return isAdmin; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
}
