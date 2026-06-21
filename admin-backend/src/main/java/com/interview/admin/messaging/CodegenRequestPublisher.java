package com.interview.admin.messaging;

import com.interview.admin.config.QueueProperties;
import com.interview.admin.dto.CodegenRequestMessage;
import com.interview.admin.model.GenerationJob;
import org.springframework.amqp.AmqpException;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Component;

@Component
public class CodegenRequestPublisher {

    private final RabbitTemplate rabbitTemplate;
    private final QueueProperties queueProperties;

    public CodegenRequestPublisher(RabbitTemplate rabbitTemplate, QueueProperties queueProperties) {
        this.rabbitTemplate = rabbitTemplate;
        this.queueProperties = queueProperties;
    }

    @Retryable(retryFor = AmqpException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public void publishDesignPreview(GenerationJob job) {
        CodegenRequestMessage msg = new CodegenRequestMessage(
            "DESIGN_PREVIEW",
            job.getId().toString(),
            job.getPrompt(),
            job.getLanguages(),
            job.getTiers(),
            job.getScenariosPerTier(),
            null,
            job.getDesignFeedback()
        );
        rabbitTemplate.convertAndSend(queueProperties.getCodegenRequest(), msg);
    }

    @Retryable(retryFor = AmqpException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public void publishFullGenerate(GenerationJob job) {
        CodegenRequestMessage msg = new CodegenRequestMessage(
            "FULL_GENERATE",
            job.getId().toString(),
            job.getPrompt(),
            job.getLanguages(),
            job.getTiers(),
            job.getScenariosPerTier(),
            job.getDesignJson(),
            null
        );
        rabbitTemplate.convertAndSend(queueProperties.getCodegenRequest(), msg);
    }
}
