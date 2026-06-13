package com.interview.platform.service;

import com.interview.platform.model.Challenge;
import com.interview.platform.repository.ChallengeRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ChallengeService {

    private final ChallengeRepository challengeRepository;

    public List<Challenge> getAllChallenges() {
        return challengeRepository.findAll();
    }

    public Challenge getChallengeById(String id) {
        return challengeRepository.findById(id).orElse(null);
    }
}
