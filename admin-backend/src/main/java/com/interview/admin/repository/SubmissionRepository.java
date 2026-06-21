package com.interview.admin.repository;

import com.interview.admin.model.Submission;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface SubmissionRepository extends JpaRepository<Submission, UUID> {
    Page<Submission> findAllByOrderBySubmittedAtDesc(Pageable pageable);
    Page<Submission> findByUserIdOrderBySubmittedAtDesc(UUID userId, Pageable pageable);
    Page<Submission> findByProblemIdOrderBySubmittedAtDesc(UUID problemId, Pageable pageable);
}
