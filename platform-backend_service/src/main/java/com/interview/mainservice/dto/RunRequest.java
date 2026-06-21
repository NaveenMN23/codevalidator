package com.interview.mainservice.dto;

import java.util.Map;

public record RunRequest(Map<String, String> files) {
}
