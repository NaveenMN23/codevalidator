package com.interview.mainservice.controller;

import com.interview.mainservice.dto.PageResponse;
import com.interview.mainservice.dto.ProblemDetailResponse;
import com.interview.mainservice.dto.ProblemSummaryResponse;
import com.interview.mainservice.service.ProblemService;
import java.util.Map;
import java.util.UUID;
import org.springframework.data.domain.Pageable;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/problems")
public class ProblemController {

    private final ProblemService problemService;

    public ProblemController(ProblemService problemService) {
        this.problemService = problemService;
    }

    @GetMapping
    public PageResponse<ProblemSummaryResponse> listProblems(Pageable pageable) {
        return problemService.listProblems(pageable);
    }

    @GetMapping("/{id}")
    public ProblemDetailResponse getProblem(@PathVariable UUID id) {
        return problemService.getProblem(id);
    }

    @GetMapping("/{id}/files")
    public Map<String, String> getProblemFiles(@PathVariable UUID id) {
        return problemService.getProblemFiles(id);
    }
}
