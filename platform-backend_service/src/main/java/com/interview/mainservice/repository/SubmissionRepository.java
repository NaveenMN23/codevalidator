package com.interview.mainservice.repository;

import com.interview.mainservice.model.Submission;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SubmissionRepository extends JpaRepository<Submission, UUID> {
}
