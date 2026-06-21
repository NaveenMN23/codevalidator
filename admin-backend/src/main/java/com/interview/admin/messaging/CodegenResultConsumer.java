package com.interview.admin.messaging;

import com.interview.admin.dto.CodegenResultMessage;
import com.interview.admin.service.GenerationService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import java.util.UUID;

@Component
public class CodegenResultConsumer {

    private static final Logger log = LoggerFactory.getLogger(CodegenResultConsumer.class);

    private final GenerationService generationService;

    public CodegenResultConsumer(GenerationService generationService) {
        this.generationService = generationService;
    }

    @RabbitListener(queues = "${app.queues.codegen-results}")
    public void onResult(CodegenResultMessage message) {
        log.info("Received codegen result: type={} jobId={} status={}", message.type(), message.jobId(), message.status());
        try {
            UUID jobId = UUID.fromString(message.jobId());
            generationService.updateFromResult(jobId, message.type(), message.status(), message.payload());
        } catch (Exception e) {
            log.error("Failed to process codegen result for jobId={}: {}", message.jobId(), e.getMessage(), e);
        }
    }
}
