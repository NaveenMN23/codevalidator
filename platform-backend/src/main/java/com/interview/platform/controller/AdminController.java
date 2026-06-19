package com.interview.platform.controller;

import com.interview.platform.service.BlueprintService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import java.util.Map;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class AdminController {

    private final BlueprintService blueprintService;

    @PostMapping("/challenges/generate")
    public ResponseEntity<?> generateChallenge() {
        // Logic to make an HTTP call to the Python CodeGen service
        return ResponseEntity.ok("Triggered code generation service");
    }

    @PostMapping("/blueprints")
    public ResponseEntity<?> saveBlueprint(@RequestBody Map<String, Object> payload) {
        String challengeId = (String) payload.get("problemId");
        if (challengeId == null) {
            return ResponseEntity.badRequest().body("problemId is required");
        }
        blueprintService.saveBlueprint(challengeId, payload);
        return ResponseEntity.ok("Blueprint saved and cached successfully");
    }

    @GetMapping("/analytics")
    public ResponseEntity<?> getAnalytics() {
        return ResponseEntity.ok("Platform analytics data");
    }
}
