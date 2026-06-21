package com.interview.admin.repository;

import com.interview.admin.model.Problem;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface ProblemRepository extends JpaRepository<Problem, UUID> {
    Optional<Problem> findBySlug(String slug);
    Page<Problem> findAllByOrderByCreatedAtDesc(Pageable pageable);
}
