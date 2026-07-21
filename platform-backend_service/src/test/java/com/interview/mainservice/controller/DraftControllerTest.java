package com.interview.mainservice.controller;

import static org.hamcrest.Matchers.is;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.logging.RequestLoggingFilter;
import com.interview.mainservice.logging.TraceIdFilter;
import com.interview.mainservice.security.JwtAuthenticationFilter;
import com.interview.mainservice.service.DraftService;
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
import org.springframework.test.web.servlet.MockMvc;

@ExtendWith(SpringExtension.class)
@WebMvcTest(DraftController.class)
@AutoConfigureMockMvc(addFilters = false)
class DraftControllerTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID PROBLEM_ID = UUID.randomUUID();

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockitoBean
    private DraftService draftService;

    // Not exercised directly (addFilters = false skips the real filter chain), but
    // SecurityConfig#securityFilterChain requires these as constructor args, so the
    // context can't load without them being satisfiable beans.
    @MockitoBean
    private JwtAuthenticationFilter jwtAuthenticationFilter;

    @MockitoBean
    private RequestLoggingFilter requestLoggingFilter;

    @MockitoBean
    private TraceIdFilter traceIdFilter;

    // addFilters = false skips Spring Security's own filter chain entirely, including the
    // filter that normally copies a saved SecurityContext back into SecurityContextHolder.
    // So the usual SecurityMockMvcRequestPostProcessors.authentication(...) postprocessor
    // (which only saves into the session) never gets picked up. Setting the holder directly
    // works instead, since MockMvc runs synchronously on this thread.
    private static void authenticateAs(UUID userId) {
        SecurityContextHolder.getContext()
                .setAuthentication(new UsernamePasswordAuthenticationToken(userId, null, List.of()));
    }

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void getDraft_returns200WithFilesPendingTimeAndUpdatedAt_whenDraftExists() throws Exception {
        Instant updatedAt = Instant.parse("2026-07-21T06:21:50.466831Z");
        DraftService.DraftData data = new DraftService.DraftData(Map.of("index.js", "code"), 120, updatedAt);
        when(draftService.getDraft(USER_ID, PROBLEM_ID)).thenReturn(Optional.of(data));
        authenticateAs(USER_ID);

        mockMvc.perform(get("/api/v1/drafts/{problemId}", PROBLEM_ID))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.files['index.js']", is("code")))
                .andExpect(jsonPath("$.pendingTime", is(120)))
                .andExpect(jsonPath("$.updatedAt", is(updatedAt.toString())));
    }

    @Test
    void getDraft_returns404_whenNoDraftExists() throws Exception {
        when(draftService.getDraft(USER_ID, PROBLEM_ID)).thenReturn(Optional.empty());
        authenticateAs(USER_ID);

        mockMvc.perform(get("/api/v1/drafts/{problemId}", PROBLEM_ID))
                .andExpect(status().isNotFound());
    }

    @Test
    void getDraft_returns401_whenUnauthenticated() throws Exception {
        mockMvc.perform(get("/api/v1/drafts/{problemId}", PROBLEM_ID))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void saveDraft_returns400_whenFilesMissingFromBody() throws Exception {
        authenticateAs(USER_ID);

        mockMvc.perform(put("/api/v1/drafts/{problemId}", PROBLEM_ID)
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(Map.of("pendingTime", 30))))
                .andExpect(status().isBadRequest());
    }

    @Test
    void saveDraft_returns200AndDelegatesToService_whenValid() throws Exception {
        authenticateAs(USER_ID);
        Map<String, Object> body = Map.of("files", Map.of("index.js", "code"), "pendingTime", 30);

        mockMvc.perform(put("/api/v1/drafts/{problemId}", PROBLEM_ID)
                        .contentType("application/json")
                        .content(objectMapper.writeValueAsString(body)))
                .andExpect(status().isOk());

        verify(draftService).saveDraft(eq(USER_ID), eq(PROBLEM_ID), any(), eq(30));
    }

    @Test
    void deleteDraft_returns204AndDelegatesToService() throws Exception {
        authenticateAs(USER_ID);

        mockMvc.perform(delete("/api/v1/drafts/{problemId}", PROBLEM_ID))
                .andExpect(status().isNoContent());

        verify(draftService).deleteDraft(USER_ID, PROBLEM_ID);
    }
}
