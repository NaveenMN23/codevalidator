package com.interview.mainservice.controller;

import com.interview.mainservice.service.DraftService;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/drafts")
public class DraftController {

    private final DraftService draftService;

    public DraftController(DraftService draftService) {
        this.draftService = draftService;
    }

    @GetMapping("/{problemId}")
    public ResponseEntity<Map<String, Object>> getDraft(@PathVariable UUID problemId,
                                                         @AuthenticationPrincipal UUID userId) {
        Optional<Map<String, String>> files = draftService.getDraft(userId, problemId);
        if (files.isEmpty() || files.get() == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(Map.of("files", files.get()));
    }

    @PutMapping("/{problemId}")
    public ResponseEntity<Void> saveDraft(@PathVariable UUID problemId,
                                           @AuthenticationPrincipal UUID userId,
                                           @RequestBody Map<String, Object> body) {
        @SuppressWarnings("unchecked")
        Map<String, String> files = (Map<String, String>) body.get("files");
        if (files == null) {
            return ResponseEntity.badRequest().build();
        }
        draftService.saveDraft(userId, problemId, files);
        return ResponseEntity.ok().build();
    }

    @DeleteMapping("/{problemId}")
    public ResponseEntity<Void> deleteDraft(@PathVariable UUID problemId,
                                             @AuthenticationPrincipal UUID userId) {
        draftService.deleteDraft(userId, problemId);
        return ResponseEntity.noContent().build();
    }
}
