package com.interview.platform.repository;
import com.interview.platform.model.Submission;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.UUID;
public interface SubmissionRepository extends JpaRepository<Submission, UUID> {}
