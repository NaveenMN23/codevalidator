package com.interview.platform.dto;

import lombok.Data;
import java.util.UUID;

@Data
public class AuthResponse {
    private UUID id;
    private String email;
    private String username;
    private String name;
}
