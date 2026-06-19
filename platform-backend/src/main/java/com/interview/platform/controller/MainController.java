package com.interview.platform.controller;

import com.interview.platform.dto.DraftRequest;
import com.interview.platform.dto.SubmissionRequest;
import com.interview.platform.service.ChallengeService;
import com.interview.platform.service.DraftService;
import com.interview.platform.service.SubmissionService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import java.util.UUID;
import java.util.Map;

@RestController
@RequestMapping("/api/main")
@RequiredArgsConstructor
public class MainController {

    private final ChallengeService challengeService;
    private final DraftService draftService;
    private final SubmissionService submissionService;

    @GetMapping("/challenges")
    public ResponseEntity<?> getChallenges() {
        return ResponseEntity.ok(challengeService.getAllChallenges());
    }

    @GetMapping("/challenges/{id}")
    public ResponseEntity<?> getChallenge(@PathVariable String id) {
        return ResponseEntity.ok(challengeService.getChallengeById(id));
    }

    @PutMapping("/drafts/{challengeId}")
    public ResponseEntity<?> saveDraft(@PathVariable String challengeId, @RequestBody DraftRequest request) {
        draftService.saveDraft(request.getUserId(), challengeId, request.getFiles());
        return ResponseEntity.ok("Draft saved");
    }

    @GetMapping("/drafts/{challengeId}")
    public ResponseEntity<?> getDraft(@PathVariable String challengeId, @RequestParam UUID userId) {
        Map<String, String> draft = draftService.getDraft(userId, challengeId);
        if (draft == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(draft);
    }

    @DeleteMapping("/drafts/{challengeId}")
    public ResponseEntity<?> deleteDraft(@PathVariable String challengeId, @RequestParam UUID userId) {
        draftService.deleteDraft(userId, challengeId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/submissions")
    public ResponseEntity<?> submitCode(@RequestBody SubmissionRequest request) {
        return ResponseEntity.accepted().body(submissionService.submit(
            request.getUserId(), 
            request.getChallengeId(), 
            request.getFiles(),
            request.isPremium(),
            request.getRemainingTimeSeconds(),
            request.getUserType()
        ));
    }

    @GetMapping("/submissions/{id}")
    public ResponseEntity<?> getSubmission(@PathVariable UUID id) {
        return ResponseEntity.ok(submissionService.getSubmission(id));
    }
}
