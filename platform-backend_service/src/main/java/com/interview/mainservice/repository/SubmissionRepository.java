package com.interview.mainservice.repository;

import com.interview.mainservice.model.Submission;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SubmissionRepository extends JpaRepository<Submission, UUID> {
    List<Submission> findByUserIdAndProblemIdOrderBySubmittedAtDesc(UUID userId, UUID problemId);

    Optional<Submission> findByIdAndUserIdAndProblemId(UUID id, UUID userId, UUID problemId);
}
