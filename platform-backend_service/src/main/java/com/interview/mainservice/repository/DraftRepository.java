package com.interview.mainservice.repository;

import com.interview.mainservice.model.Draft;
import com.interview.mainservice.model.DraftId;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DraftRepository extends JpaRepository<Draft, DraftId> {
}
