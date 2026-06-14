package com.interview.platform.service;

import com.interview.platform.config.RabbitMQConfig;
import com.interview.platform.dto.GradingJob;
import com.interview.platform.model.Challenge;
import com.interview.platform.model.Submission;
import com.interview.platform.model.User;
import com.interview.platform.repository.ChallengeRepository;
import com.interview.platform.repository.SubmissionRepository;
import com.interview.platform.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.AmqpException;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.dao.DataAccessException;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class SubmissionService {

    private final SubmissionRepository submissionRepository;
    private final UserRepository userRepository;
    private final ChallengeRepository challengeRepository;
    private final RabbitTemplate rabbitTemplate;

    @Transactional
    @Retryable(
            value = {DataAccessException.class, AmqpException.class},
            maxAttempts = 3,
            backoff = @Backoff(delay = 1000, multiplier = 2.0)
    )
    public Submission submit(UUID userId, String challengeId, Map<String, String> files) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));
        Challenge challenge = challengeRepository.findById(challengeId)
                .orElseThrow(() -> new RuntimeException("Challenge not found"));

        Submission submission = Submission.builder()
                .user(user)
                .challenge(challenge)
                .status("PENDING")
                .build();

        submission = submissionRepository.save(submission);

        GradingJob job = GradingJob.builder()
                .submissionId(submission.getId())
                .challengeId(challengeId)
                .language(challenge.getLanguage())
                .files(files)
                .build();

        rabbitTemplate.convertAndSend(RabbitMQConfig.EXCHANGE, RabbitMQConfig.ROUTING_KEY, job);

        return submission;
    }
}
