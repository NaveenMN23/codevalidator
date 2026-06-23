package com.interview.admin.dto;

import java.util.List;

public record CodegenRequestMessage(
    String type,
    String jobId,
    String prompt,
    List<String> languages,
    List<String> tiers,
    int scenariosPerTier,
    int debugScenariosPerTier,
    String designJson,
    String feedback
) {}
