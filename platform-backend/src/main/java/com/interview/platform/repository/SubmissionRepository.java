package com.interview.platform.repository;

import com.interview.platform.model.Submission;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

public interface SubmissionRepository extends JpaRepository<Submission, UUID> {

    // For attempt history (progressive feedback — most recent first)
    List<Submission> findByUserIdAndChallengeIdOrderByCreatedAtDesc(UUID userId, String challengeId);

    // For session report (all submissions in a session, chronological)
    List<Submission> findBySessionIdOrderByCreatedAtAsc(UUID sessionId);

    // For auto-incrementing attempt_number
    int countByUserIdAndChallengeId(UUID userId, String challengeId);
}
