package com.interview.mainservice.repository;

import com.interview.mainservice.model.Draft;
import com.interview.mainservice.model.DraftId;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DraftRepository extends JpaRepository<Draft, DraftId> {
    java.util.Optional<Draft> findByUserIdAndProblemId(java.util.UUID userId, java.util.UUID problemId);
    void deleteByUserIdAndProblemId(java.util.UUID userId, java.util.UUID problemId);
}
