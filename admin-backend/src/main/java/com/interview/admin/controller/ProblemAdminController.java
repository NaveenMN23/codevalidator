package com.interview.admin.controller;

import com.interview.admin.dto.PageResponse;
import com.interview.admin.dto.ProblemRequest;
import com.interview.admin.dto.ProblemResponse;
import com.interview.admin.service.ProblemManagementService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/admin/problems")
@CrossOrigin(origins = "*")
public class ProblemAdminController {

    private final ProblemManagementService problemService;

    public ProblemAdminController(ProblemManagementService problemService) {
        this.problemService = problemService;
    }

    @GetMapping
    public ResponseEntity<PageResponse<ProblemResponse>> listProblems(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(problemService.listProblems(page, size));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ProblemResponse> getProblem(@PathVariable UUID id) {
        return ResponseEntity.ok(problemService.getProblem(id));
    }

    @PostMapping
    public ResponseEntity<ProblemResponse> createProblem(@Valid @RequestBody ProblemRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(problemService.createProblem(request));
    }

    @PutMapping("/{id}")
    public ResponseEntity<ProblemResponse> updateProblem(@PathVariable UUID id,
                                                          @Valid @RequestBody ProblemRequest request) {
        return ResponseEntity.ok(problemService.updateProblem(id, request));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteProblem(@PathVariable UUID id) {
        problemService.deleteProblem(id);
        return ResponseEntity.noContent().build();
    }

    @PatchMapping("/{id}/publish")
    public ResponseEntity<ProblemResponse> setPublished(@PathVariable UUID id,
                                                         @RequestBody Map<String, Boolean> body) {
        boolean published = Boolean.TRUE.equals(body.get("published"));
        return ResponseEntity.ok(problemService.setPublished(id, published));
    }
}
