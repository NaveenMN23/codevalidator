package com.interview.platform.service;

import com.interview.platform.model.Challenge;
import com.interview.platform.model.ChallengeDraft;
import com.interview.platform.model.User;
import com.interview.platform.repository.ChallengeDraftRepository;
import com.interview.platform.repository.ChallengeRepository;
import com.interview.platform.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
public class DraftService {

    private final ChallengeDraftRepository draftRepository;
    private final UserRepository userRepository;
    private final ChallengeRepository challengeRepository;
    private final RedisTemplate<String, Object> redisTemplate;

    private static final String DRAFT_KEY_PREFIX = "draft:";

    public void saveDraft(UUID userId, String challengeId, Map<String, String> files) {
        String redisKey = DRAFT_KEY_PREFIX + userId + ":" + challengeId;
        
        // Save to Redis for fast access
        redisTemplate.opsForValue().set(redisKey, files, 1, TimeUnit.HOURS);

        // Async or Periodic flush to DB would be better, but for now, let's just save to DB
        flushToDb(userId, challengeId, files);
    }

    @Transactional
    public void flushToDb(UUID userId, String challengeId, Map<String, String> files) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));
        Challenge challenge = challengeRepository.findById(challengeId)
                .orElseThrow(() -> new RuntimeException("Challenge not found"));

        ChallengeDraft draft = draftRepository.findByUserAndChallenge(user, challenge)
                .orElse(ChallengeDraft.builder().user(user).challenge(challenge).build());
        
        draft.setFiles(files);
        draftRepository.save(draft);
    }

    @SuppressWarnings("unchecked")
    public Map<String, String> getDraft(UUID userId, String challengeId) {
        String redisKey = DRAFT_KEY_PREFIX + userId + ":" + challengeId;
        Map<String, String> files = (Map<String, String>) redisTemplate.opsForValue().get(redisKey);

        if (files == null) {
            User user = userRepository.findById(userId)
                    .orElseThrow(() -> new RuntimeException("User not found"));
            Challenge challenge = challengeRepository.findById(challengeId)
                    .orElseThrow(() -> new RuntimeException("Challenge not found"));

            files = draftRepository.findByUserAndChallenge(user, challenge)
                    .map(ChallengeDraft::getFiles)
                    .orElse(null);
            
            if (files != null) {
                redisTemplate.opsForValue().set(redisKey, files, 1, TimeUnit.HOURS);
            }
        }

        return files;
    }

    @Transactional
    public void deleteDraft(UUID userId, String challengeId) {
        String redisKey = DRAFT_KEY_PREFIX + userId + ":" + challengeId;
        redisTemplate.delete(redisKey);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));
        Challenge challenge = challengeRepository.findById(challengeId)
                .orElseThrow(() -> new RuntimeException("Challenge not found"));

        draftRepository.deleteByUserAndChallenge(user, challenge);
    }
}
