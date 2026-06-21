package com.interview.admin.controller;

import com.interview.admin.dto.PageResponse;
import com.interview.admin.dto.SubmissionResponse;
import com.interview.admin.service.SubmissionMonitorService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/admin/submissions")
@CrossOrigin(origins = "*")
public class SubmissionMonitorController {

    private final SubmissionMonitorService monitorService;

    public SubmissionMonitorController(SubmissionMonitorService monitorService) {
        this.monitorService = monitorService;
    }

    @GetMapping
    public ResponseEntity<PageResponse<SubmissionResponse>> listSubmissions(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(monitorService.listSubmissions(page, size));
    }

    @GetMapping("/queue-depth")
    public ResponseEntity<Map<String, Integer>> getQueueDepth() {
        return ResponseEntity.ok(monitorService.getQueueDepth());
    }
}
