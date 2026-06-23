package com.interview.mainservice.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.model.Submission;
import com.interview.mainservice.repository.SubmissionRepository;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/submissions")
public class SubmissionController {

    private final SubmissionRepository submissionRepository;
    private final ObjectMapper objectMapper;

    public SubmissionController(SubmissionRepository submissionRepository, ObjectMapper objectMapper) {
        this.submissionRepository = submissionRepository;
        this.objectMapper = objectMapper;
    }

    @GetMapping("/{id}")
    public ResponseEntity<Map<String, Object>> getSubmission(@PathVariable UUID id) {
        Submission submission = submissionRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Submission not found"));

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", submission.getId().toString());
        result.put("status", submission.getStatus());
        result.put("score", submission.getScore());
        result.put("logs", null);

        if (submission.getFeedbackJson() != null) {
            try {
                result.put("feedback", objectMapper.readValue(submission.getFeedbackJson(),
                        new TypeReference<Map<String, Object>>() {}));
            } catch (JsonProcessingException e) {
                result.put("feedback", null);
            }
        } else {
            result.put("feedback", null);
        }

        return ResponseEntity.ok(result);
    }
}
