package com.interview.mainservice.repository;

import com.interview.mainservice.model.UserProblem;
import com.interview.mainservice.model.UserProblemId;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserProblemRepository extends JpaRepository<UserProblem, UserProblemId> {
}
