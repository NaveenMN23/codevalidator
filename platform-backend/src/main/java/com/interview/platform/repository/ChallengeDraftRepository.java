package com.interview.platform.repository;
import com.interview.platform.model.ChallengeDraft;
import com.interview.platform.model.User;
import com.interview.platform.model.Challenge;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.UUID;
import java.util.Optional;
public interface ChallengeDraftRepository extends JpaRepository<ChallengeDraft, UUID> {
    Optional<ChallengeDraft> findByUserAndChallenge(User user, Challenge challenge);
    void deleteByUserAndChallenge(User user, Challenge challenge);
}
