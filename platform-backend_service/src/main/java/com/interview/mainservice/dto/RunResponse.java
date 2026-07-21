package com.interview.mainservice.dto;

import java.util.List;

public record RunResponse(boolean success, String stdout, String stderr, int exitCode,
        List<TestCaseResult> testResults) {
}
