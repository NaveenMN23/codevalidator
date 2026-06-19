package com.interview.mainservice.dto;

import java.util.UUID;

public record UserProfileResponse(UUID id, String email, String displayName) {
}
