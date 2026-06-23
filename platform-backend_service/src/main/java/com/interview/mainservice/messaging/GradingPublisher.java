package com.interview.mainservice.messaging;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class GradingPublisher {

    private static final Logger log = LoggerFactory.getLogger(GradingPublisher.class);

    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;

    @Value("${app.grading-queue:grading-queue}")
    private String gradingQueue;

    public GradingPublisher(RabbitTemplate rabbitTemplate, ObjectMapper objectMapper) {
        this.rabbitTemplate = rabbitTemplate;
        this.objectMapper = objectMapper;
    }

    public void publishGradingRequest(UUID submissionId, UUID problemId, UUID userId,
                                       String filesJson, int remainingTimeSeconds, String userType) {
        try {
            String message = objectMapper.writeValueAsString(Map.of(
                    "submissionId", submissionId.toString(),
                    "problemId", problemId.toString(),
                    "userId", userId.toString(),
                    "filesJson", filesJson,
                    "remainingTime", remainingTimeSeconds,
                    "userType", userType
            ));
            rabbitTemplate.convertAndSend(gradingQueue, message);
            log.info("Published grading request for submission {}", submissionId);
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize grading message for submission {}: {}", submissionId, e.getMessage());
        }
    }
}
