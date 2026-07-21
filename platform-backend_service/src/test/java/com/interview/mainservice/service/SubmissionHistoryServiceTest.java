package com.interview.mainservice.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.model.Submission;
import com.interview.mainservice.repository.SubmissionRepository;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class SubmissionHistoryServiceTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID PROBLEM_ID = UUID.randomUUID();
    private static final UUID SUBMISSION_ID = UUID.randomUUID();

    @Mock
    private SubmissionRepository submissionRepository;

    private SubmissionHistoryService submissionHistoryService;

    @BeforeEach
    void setUp() {
        submissionHistoryService = new SubmissionHistoryService(submissionRepository, new ObjectMapper());
    }

    private static Submission submissionWith(String filesJson, Instant submittedAt) {
        Submission submission = new Submission(USER_ID, PROBLEM_ID, "", submittedAt);
        submission.setStatus("COMPLETED");
        submission.setScore(100.0);
        submission.setLogs("ok");
        submission.setFilesJson(filesJson);
        ReflectionTestUtils.setField(submission, "id", SUBMISSION_ID);
        return submission;
    }

    @Test
    void listSubmissions_delegatesToRepository_orderedNewestFirst() {
        Submission submission = submissionWith("{}", Instant.now());
        when(submissionRepository.findByUserIdAndProblemIdOrderBySubmittedAtDesc(USER_ID, PROBLEM_ID))
                .thenReturn(List.of(submission));

        List<Submission> result = submissionHistoryService.listSubmissions(USER_ID, PROBLEM_ID);

        assertThat(result).containsExactly(submission);
    }

    @Test
    void getSubmission_returnsDetailWithDeserializedFiles_whenFilesJsonIsValid() {
        Instant submittedAt = Instant.parse("2026-07-21T06:21:50.466831Z");
        Submission submission = submissionWith("{\"index.js\":\"code\"}", submittedAt);
        when(submissionRepository.findByIdAndUserIdAndProblemId(SUBMISSION_ID, USER_ID, PROBLEM_ID))
                .thenReturn(Optional.of(submission));

        Optional<SubmissionHistoryService.SubmissionDetail> result =
                submissionHistoryService.getSubmission(USER_ID, PROBLEM_ID, SUBMISSION_ID);

        assertThat(result).isPresent();
        assertThat(result.get().files()).containsEntry("index.js", "code");
        assertThat(result.get().status()).isEqualTo("COMPLETED");
        assertThat(result.get().score()).isEqualTo(100.0);
        assertThat(result.get().logs()).isEqualTo("ok");
        assertThat(result.get().submittedAt()).isEqualTo(submittedAt);
    }

    @Test
    void getSubmission_returnsEmptyFiles_whenFilesJsonIsNull() {
        Submission submission = submissionWith(null, Instant.now());
        when(submissionRepository.findByIdAndUserIdAndProblemId(SUBMISSION_ID, USER_ID, PROBLEM_ID))
                .thenReturn(Optional.of(submission));

        Optional<SubmissionHistoryService.SubmissionDetail> result =
                submissionHistoryService.getSubmission(USER_ID, PROBLEM_ID, SUBMISSION_ID);

        assertThat(result).isPresent();
        assertThat(result.get().files()).isEmpty();
    }

    @Test
    void getSubmission_returnsEmptyFiles_whenFilesJsonIsMalformed() {
        Submission submission = submissionWith("{not-valid-json", Instant.now());
        when(submissionRepository.findByIdAndUserIdAndProblemId(SUBMISSION_ID, USER_ID, PROBLEM_ID))
                .thenReturn(Optional.of(submission));

        Optional<SubmissionHistoryService.SubmissionDetail> result =
                submissionHistoryService.getSubmission(USER_ID, PROBLEM_ID, SUBMISSION_ID);

        assertThat(result).isPresent();
        assertThat(result.get().files()).isEmpty();
    }

    @Test
    void getSubmission_returnsEmpty_whenNoMatchingSubmission() {
        when(submissionRepository.findByIdAndUserIdAndProblemId(SUBMISSION_ID, USER_ID, PROBLEM_ID))
                .thenReturn(Optional.empty());

        assertThat(submissionHistoryService.getSubmission(USER_ID, PROBLEM_ID, SUBMISSION_ID)).isEmpty();
    }
}
