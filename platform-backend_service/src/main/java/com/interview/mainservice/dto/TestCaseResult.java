package com.interview.mainservice.dto;

public record TestCaseResult(
        String name,
        String className,
        Status status,
        String message,
        String expected,
        String actual,
        String stackTrace) {

    public enum Status {
        PASSED, FAILED, ERRORED, SKIPPED
    }
}
