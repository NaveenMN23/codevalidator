package com.interview.admin.dto;

import com.interview.admin.model.User;

import java.time.Instant;
import java.util.UUID;

public record UserResponse(
    UUID id,
    String email,
    String displayName,
    boolean isAdmin,
    Instant createdAt
) {
    public static UserResponse from(User u) {
        return new UserResponse(u.getId(), u.getEmail(), u.getDisplayName(), u.isAdmin(), u.getCreatedAt());
    }
}
