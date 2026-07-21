package com.interview.mainservice.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.model.Draft;
import com.interview.mainservice.repository.DraftRepository;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class DraftServiceTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID PROBLEM_ID = UUID.randomUUID();

    @Mock
    private DraftRepository draftRepository;

    private DraftService draftService;

    @BeforeEach
    void setUp() {
        draftService = new DraftService(draftRepository, new ObjectMapper());
    }

    private static Draft draftWith(String filesJson, Instant updatedAt) {
        Draft draft = new Draft(USER_ID, PROBLEM_ID, "");
        draft.setFilesJson(filesJson);
        ReflectionTestUtils.setField(draft, "updatedAt", updatedAt);
        return draft;
    }

    @Test
    void getDraft_returnsFilesPendingTimeAndUpdatedAt_whenDraftHasValidJson() {
        Instant updatedAt = Instant.parse("2026-07-21T06:21:50.466831Z");
        Draft draft = draftWith("{\"index.js\":\"code\"}", updatedAt);
        draft.setPendingTime(120);
        when(draftRepository.findByUserIdAndProblemId(USER_ID, PROBLEM_ID)).thenReturn(Optional.of(draft));

        Optional<DraftService.DraftData> result = draftService.getDraft(USER_ID, PROBLEM_ID);

        assertThat(result).isPresent();
        assertThat(result.get().files()).containsEntry("index.js", "code");
        assertThat(result.get().pendingTime()).isEqualTo(120);
        assertThat(result.get().updatedAt()).isEqualTo(updatedAt);
    }

    @Test
    void getDraft_returnsEmpty_whenNoDraftRowExists() {
        when(draftRepository.findByUserIdAndProblemId(USER_ID, PROBLEM_ID)).thenReturn(Optional.empty());

        assertThat(draftService.getDraft(USER_ID, PROBLEM_ID)).isEmpty();
    }

    @Test
    void getDraft_returnsEmpty_whenFilesJsonIsNull() {
        Draft draft = draftWith(null, Instant.now());
        when(draftRepository.findByUserIdAndProblemId(USER_ID, PROBLEM_ID)).thenReturn(Optional.of(draft));

        assertThat(draftService.getDraft(USER_ID, PROBLEM_ID)).isEmpty();
    }

    @Test
    void getDraft_returnsEmpty_whenFilesJsonIsMalformed() {
        Draft draft = draftWith("{not-valid-json", Instant.now());
        when(draftRepository.findByUserIdAndProblemId(USER_ID, PROBLEM_ID)).thenReturn(Optional.of(draft));

        assertThat(draftService.getDraft(USER_ID, PROBLEM_ID)).isEmpty();
    }

    @Test
    void saveDraft_createsNewDraft_whenNoneExistsYet() {
        when(draftRepository.findByUserIdAndProblemId(USER_ID, PROBLEM_ID)).thenReturn(Optional.empty());

        draftService.saveDraft(USER_ID, PROBLEM_ID, Map.of("index.js", "code"), 45);

        ArgumentCaptor<Draft> captor = ArgumentCaptor.forClass(Draft.class);
        verify(draftRepository).save(captor.capture());
        assertThat(captor.getValue().getUserId()).isEqualTo(USER_ID);
        assertThat(captor.getValue().getProblemId()).isEqualTo(PROBLEM_ID);
        assertThat(captor.getValue().getFilesJson()).contains("index.js");
        assertThat(captor.getValue().getPendingTime()).isEqualTo(45);
    }

    @Test
    void saveDraft_updatesExistingDraftInPlace_whenOneAlreadyExists() {
        Draft existing = draftWith("{}", Instant.now());
        when(draftRepository.findByUserIdAndProblemId(USER_ID, PROBLEM_ID)).thenReturn(Optional.of(existing));

        draftService.saveDraft(USER_ID, PROBLEM_ID, Map.of("a.js", "1"), 10);

        verify(draftRepository).save(existing);
        assertThat(existing.getFilesJson()).contains("a.js");
        assertThat(existing.getPendingTime()).isEqualTo(10);
    }

    @Test
    void deleteDraft_delegatesToRepository() {
        draftService.deleteDraft(USER_ID, PROBLEM_ID);

        verify(draftRepository).deleteByUserIdAndProblemId(USER_ID, PROBLEM_ID);
    }
}
