package com.interview.mainservice.controller;

import com.interview.mainservice.dto.SubmissionDetailResponse;
import com.interview.mainservice.dto.SubmissionSummaryResponse;
import com.interview.mainservice.model.Submission;
import com.interview.mainservice.service.SubmissionHistoryService;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/problems/{problemId}/submissions")
public class SubmissionController {

    private final SubmissionHistoryService submissionHistoryService;

    public SubmissionController(SubmissionHistoryService submissionHistoryService) {
        this.submissionHistoryService = submissionHistoryService;
    }

    @GetMapping
    public ResponseEntity<List<SubmissionSummaryResponse>> listSubmissions(@PathVariable UUID problemId,
                                                                            @AuthenticationPrincipal UUID userId) {
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        List<SubmissionSummaryResponse> submissions = submissionHistoryService.listSubmissions(userId, problemId)
                .stream()
                .map(this::toSummary)
                .toList();
        return ResponseEntity.ok(submissions);
    }

    @GetMapping("/{submissionId}")
    public ResponseEntity<SubmissionDetailResponse> getSubmission(@PathVariable UUID problemId,
                                                                    @PathVariable UUID submissionId,
                                                                    @AuthenticationPrincipal UUID userId) {
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }
        Optional<SubmissionHistoryService.SubmissionDetail> detail =
                submissionHistoryService.getSubmission(userId, problemId, submissionId);
        return detail.map(d -> ResponseEntity.ok(new SubmissionDetailResponse(
                        d.id(), d.status(), d.score(), d.logs(), d.submittedAt(), d.files())))
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    private SubmissionSummaryResponse toSummary(Submission submission) {
        return new SubmissionSummaryResponse(submission.getId(), submission.getStatus(),
                submission.getScore(), submission.getSubmittedAt());
    }
}
