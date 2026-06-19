package com.interview.mainservice.model;

import java.io.Serializable;
import java.util.Objects;
import java.util.UUID;

public class UserProblemId implements Serializable {

    private UUID userId;
    private UUID problemId;

    protected UserProblemId() {
    }

    public UserProblemId(UUID userId, UUID problemId) {
        this.userId = userId;
        this.problemId = problemId;
    }

    public UUID getUserId() {
        return userId;
    }

    public UUID getProblemId() {
        return problemId;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof UserProblemId that)) {
            return false;
        }
        return Objects.equals(userId, that.userId) && Objects.equals(problemId, that.problemId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(userId, problemId);
    }
}
