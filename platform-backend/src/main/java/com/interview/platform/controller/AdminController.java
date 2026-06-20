package com.interview.platform.controller;

import com.interview.platform.model.InterviewSession;
import com.interview.platform.model.User;
import com.interview.platform.repository.InterviewSessionRepository;
import com.interview.platform.repository.SubmissionRepository;
import com.interview.platform.repository.UserRepository;
import com.interview.platform.service.BlueprintService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class AdminController {

    private final BlueprintService blueprintService;
    private final InterviewSessionRepository sessionRepository;
    private final SubmissionRepository submissionRepository;
    private final UserRepository userRepository;

    @PostMapping("/challenges/generate")
    public ResponseEntity<?> generateChallenge() {
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

    @GetMapping("/blueprints/{challengeId}")
    public ResponseEntity<?> getBlueprint(@PathVariable String challengeId) {
        return blueprintService.findBlueprint(challengeId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/analytics")
    public ResponseEntity<?> getAnalytics() {
        return ResponseEntity.ok("Platform analytics data");
    }

    // ── Interview Sessions ────────────────────────────────────────────────────

    @PostMapping("/sessions")
    public ResponseEntity<?> createSession(@RequestBody Map<String, Object> payload) {
        UUID candidateId = UUID.fromString((String) payload.get("candidateId"));
        User candidate = userRepository.findById(candidateId)
                .orElseThrow(() -> new RuntimeException("Candidate not found"));

        InterviewSession.InterviewSessionBuilder builder = InterviewSession.builder()
                .candidate(candidate)
                .challengeIds((List<String>) payload.get("challengeIds"))
                .status("SCHEDULED");

        if (payload.get("interviewerId") != null) {
            UUID interviewerId = UUID.fromString((String) payload.get("interviewerId"));
            userRepository.findById(interviewerId).ifPresent(builder::interviewer);
        }

        InterviewSession session = sessionRepository.save(builder.build());
        return ResponseEntity.ok(Map.of("sessionId", session.getId().toString()));
    }

    @GetMapping("/sessions/{sessionId}/report")
    public ResponseEntity<?> getSessionReport(@PathVariable UUID sessionId) {
        InterviewSession session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new RuntimeException("Session not found"));

        var submissions = submissionRepository.findBySessionIdOrderByCreatedAtAsc(sessionId);
        return ResponseEntity.ok(Map.of(
                "session", Map.of(
                        "id", session.getId(),
                        "candidateId", session.getCandidate().getId(),
                        "status", session.getStatus(),
                        "challengeIds", session.getChallengeIds(),
                        "createdAt", session.getCreatedAt()
                ),
                "submissions", submissions
        ));
    }

    @GetMapping("/users/{userId}/submissions")
    public ResponseEntity<?> getUserSubmissions(@PathVariable UUID userId) {
        // Returns all submissions grouped by challenge, most recent first
        var submissions = submissionRepository.findAll().stream()
                .filter(s -> s.getUser().getId().equals(userId))
                .sorted((a, b) -> b.getCreatedAt().compareTo(a.getCreatedAt()))
                .toList();
        return ResponseEntity.ok(submissions);
    }
}
