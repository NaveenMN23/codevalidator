package com.interview.admin.repository;

import com.interview.admin.model.GenerationJob;
import com.interview.admin.model.GenerationJobStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface GenerationJobRepository extends JpaRepository<GenerationJob, UUID> {
    List<GenerationJob> findAllByOrderByCreatedAtDesc();
    Page<GenerationJob> findByStatus(GenerationJobStatus status, Pageable pageable);
}
