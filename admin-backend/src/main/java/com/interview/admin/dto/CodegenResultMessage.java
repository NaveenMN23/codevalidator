package com.interview.admin.dto;

public record CodegenResultMessage(
    String type,
    String jobId,
    String status,
    Object payload
) {}
