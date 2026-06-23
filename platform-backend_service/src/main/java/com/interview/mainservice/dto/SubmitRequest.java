package com.interview.mainservice.dto;

import java.util.Map;

public record SubmitRequest(Map<String, String> files, Integer remainingTimeSeconds, String userType) {
}
