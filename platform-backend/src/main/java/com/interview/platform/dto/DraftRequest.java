package com.interview.platform.dto;

import lombok.Data;
import java.util.Map;
import java.util.UUID;

@Data
public class DraftRequest {
    private UUID userId;
    private Map<String, String> files;
}
