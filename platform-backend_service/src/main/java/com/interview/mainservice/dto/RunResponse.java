package com.interview.mainservice.dto;

public record RunResponse(boolean success, String stdout, String stderr, int exitCode) {
}
