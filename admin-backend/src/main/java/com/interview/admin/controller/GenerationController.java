package com.interview.admin.controller;

import com.interview.admin.dto.GenerationJobResponse;
import com.interview.admin.dto.GenerationPreviewRequest;
import com.interview.admin.dto.GenerationRefineRequest;
import com.interview.admin.service.GenerationService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/admin/generation")
@CrossOrigin(origins = "*")
public class GenerationController {

    private final GenerationService generationService;

    public GenerationController(GenerationService generationService) {
        this.generationService = generationService;
    }

    @PostMapping("/preview")
    public ResponseEntity<GenerationJobResponse> previewDesign(@Valid @RequestBody GenerationPreviewRequest request) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(generationService.previewDesign(request));
    }

    @PostMapping("/{jobId}/refine")
    public ResponseEntity<GenerationJobResponse> refineDesign(@PathVariable UUID jobId,
                                                               @Valid @RequestBody GenerationRefineRequest request) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(generationService.refineDesign(jobId, request.feedback()));
    }

    @PostMapping("/{jobId}/approve")
    public ResponseEntity<GenerationJobResponse> approveAndGenerate(@PathVariable UUID jobId) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(generationService.approveAndGenerate(jobId));
    }

    @GetMapping("/{jobId}/status")
    public ResponseEntity<GenerationJobResponse> getStatus(@PathVariable UUID jobId) {
        return ResponseEntity.ok(generationService.getStatus(jobId));
    }

    @PostMapping("/{jobId}/cancel")
    public ResponseEntity<GenerationJobResponse> cancelJob(@PathVariable UUID jobId) {
        return ResponseEntity.ok(generationService.cancelJob(jobId));
    }

    @PostMapping("/{jobId}/retry")
    public ResponseEntity<GenerationJobResponse> retryJob(@PathVariable UUID jobId) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(generationService.retryJob(jobId));
    }

    @GetMapping("/history")
    public ResponseEntity<List<GenerationJobResponse>> getHistory() {
        return ResponseEntity.ok(generationService.getHistory());
    }
}
