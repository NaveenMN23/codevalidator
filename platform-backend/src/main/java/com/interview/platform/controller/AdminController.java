package com.interview.platform.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;

@RestController
@RequestMapping("/api/admin")
public class AdminController {

    @PostMapping("/challenges/generate")
    public ResponseEntity<?> generateChallenge() {
        // Logic to make an HTTP call to the Python CodeGen service
        return ResponseEntity.ok("Triggered code generation service");
    }

    @GetMapping("/analytics")
    public ResponseEntity<?> getAnalytics() {
        return ResponseEntity.ok("Platform analytics data");
    }
}
