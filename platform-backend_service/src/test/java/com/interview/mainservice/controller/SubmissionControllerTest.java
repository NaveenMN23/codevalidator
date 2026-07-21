package com.interview.mainservice.controller;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.interview.mainservice.logging.RequestLoggingFilter;
import com.interview.mainservice.logging.TraceIdFilter;
import com.interview.mainservice.model.Submission;
import com.interview.mainservice.security.JwtAuthenticationFilter;
import com.interview.mainservice.service.SubmissionHistoryService;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.junit.jupiter.SpringExtension;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.MockMvc;

@ExtendWith(SpringExtension.class)
@WebMvcTest(SubmissionController.class)
@AutoConfigureMockMvc(addFilters = false)
class SubmissionControllerTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID PROBLEM_ID = UUID.randomUUID();
    private static final UUID SUBMISSION_ID = UUID.randomUUID();

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private SubmissionHistoryService submissionHistoryService;

    // Not exercised directly (addFilters = false skips the real filter chain), but
    // SecurityConfig#securityFilterChain requires these as constructor args, so the
    // context can't load without them being satisfiable beans.
    @MockitoBean
    private JwtAuthenticationFilter jwtAuthenticationFilter;

    @MockitoBean
    private RequestLoggingFilter requestLoggingFilter;

    @MockitoBean
    private TraceIdFilter traceIdFilter;

    private static void authenticateAs(UUID userId) {
        SecurityContextHolder.getContext()
                .setAuthentication(new UsernamePasswordAuthenticationToken(userId, null, List.of()));
    }

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    private static Submission submissionWith(Instant submittedAt) {
        Submission submission = new Submission(USER_ID, PROBLEM_ID, "", submittedAt);
        submission.setStatus("COMPLETED");
        submission.setScore(100.0);
        ReflectionTestUtils.setField(submission, "id", SUBMISSION_ID);
        return submission;
    }

    @Test
    void listSubmissions_returns200WithSummaries_whenAuthenticated() throws Exception {
        Instant submittedAt = Instant.parse("2026-07-21T06:21:50.466831Z");
        when(submissionHistoryService.listSubmissions(USER_ID, PROBLEM_ID))
                .thenReturn(List.of(submissionWith(submittedAt)));
        authenticateAs(USER_ID);

        mockMvc.perform(get("/api/v1/problems/{problemId}/submissions", PROBLEM_ID))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].id", is(SUBMISSION_ID.toString())))
                .andExpect(jsonPath("$[0].status", is("COMPLETED")))
                .andExpect(jsonPath("$[0].score", is(100.0)))
                .andExpect(jsonPath("$[0].submittedAt", is(submittedAt.toString())));
    }

    @Test
    void listSubmissions_returns401_whenUnauthenticated() throws Exception {
        mockMvc.perform(get("/api/v1/problems/{problemId}/submissions", PROBLEM_ID))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void getSubmission_returns200WithFiles_whenSubmissionExists() throws Exception {
        Instant submittedAt = Instant.parse("2026-07-21T06:21:50.466831Z");
        SubmissionHistoryService.SubmissionDetail detail = new SubmissionHistoryService.SubmissionDetail(
                SUBMISSION_ID, "COMPLETED", 100.0, "ok", submittedAt, Map.of("index.js", "code"));
        when(submissionHistoryService.getSubmission(USER_ID, PROBLEM_ID, SUBMISSION_ID))
                .thenReturn(Optional.of(detail));
        authenticateAs(USER_ID);

        mockMvc.perform(get("/api/v1/problems/{problemId}/submissions/{submissionId}", PROBLEM_ID, SUBMISSION_ID))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.files['index.js']", is("code")))
                .andExpect(jsonPath("$.logs", is("ok")));
    }

    @Test
    void getSubmission_returns404_whenNoMatchingSubmission() throws Exception {
        when(submissionHistoryService.getSubmission(USER_ID, PROBLEM_ID, SUBMISSION_ID))
                .thenReturn(Optional.empty());
        authenticateAs(USER_ID);

        mockMvc.perform(get("/api/v1/problems/{problemId}/submissions/{submissionId}", PROBLEM_ID, SUBMISSION_ID))
                .andExpect(status().isNotFound());
    }

    @Test
    void getSubmission_returns401_whenUnauthenticated() throws Exception {
        mockMvc.perform(get("/api/v1/problems/{problemId}/submissions/{submissionId}", PROBLEM_ID, SUBMISSION_ID))
                .andExpect(status().isUnauthorized());
    }
}
