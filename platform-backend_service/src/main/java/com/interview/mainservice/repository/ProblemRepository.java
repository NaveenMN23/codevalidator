package com.interview.mainservice.repository;

import com.interview.mainservice.model.Problem;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ProblemRepository extends JpaRepository<Problem, UUID> {

    Optional<Problem> findBySlug(String slug);

    Page<Problem> findByIsPublishedTrue(Pageable pageable);
}
