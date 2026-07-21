package com.interview.mainservice.controller;

import com.interview.mainservice.service.DraftService;
import java.util.LinkedHashMap;
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
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        Optional<DraftService.DraftData> draft = draftService.getDraft(userId, problemId);
        if (draft.isEmpty() || draft.get() == null) {
            return ResponseEntity.notFound().build();
        }
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("files", draft.get().files());
        response.put("pendingTime", draft.get().pendingTime());
        response.put("updatedAt", draft.get().updatedAt().toString());
        return ResponseEntity.ok(response);
    }

    @PutMapping("/{problemId}")
    public ResponseEntity<Void> saveDraft(@PathVariable UUID problemId,
                                           @AuthenticationPrincipal UUID userId,
                                           @RequestBody Map<String, Object> body) {
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        @SuppressWarnings("unchecked")
        Map<String, String> files = (Map<String, String>) body.get("files");
        if (files == null) {
            return ResponseEntity.badRequest().build();
        }
        Integer pendingTime = body.get("pendingTime") instanceof Number n ? n.intValue() : null;
        draftService.saveDraft(userId, problemId, files, pendingTime);
        return ResponseEntity.ok().build();
    }

    @DeleteMapping("/{problemId}")
    public ResponseEntity<Void> deleteDraft(@PathVariable UUID problemId,
                                             @AuthenticationPrincipal UUID userId) {
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        draftService.deleteDraft(userId, problemId);
        return ResponseEntity.noContent().build();
    }
}
