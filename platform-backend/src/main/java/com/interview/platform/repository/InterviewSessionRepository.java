package com.interview.platform.repository;

import com.interview.platform.model.InterviewSession;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

public interface InterviewSessionRepository extends JpaRepository<InterviewSession, UUID> {

    List<InterviewSession> findByCandidateIdOrderByCreatedAtDesc(UUID candidateId);
    List<InterviewSession> findByInterviewerIdOrderByCreatedAtDesc(UUID interviewerId);
}
