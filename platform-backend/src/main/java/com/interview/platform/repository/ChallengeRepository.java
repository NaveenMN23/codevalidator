package com.interview.platform.repository;
import com.interview.platform.model.Challenge;
import org.springframework.data.jpa.repository.JpaRepository;
public interface ChallengeRepository extends JpaRepository<Challenge, String> {}
