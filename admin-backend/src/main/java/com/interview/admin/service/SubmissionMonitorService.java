package com.interview.admin.service;

import com.interview.admin.dto.PageResponse;
import com.interview.admin.dto.SubmissionResponse;
import com.interview.admin.repository.SubmissionRepository;
import org.springframework.amqp.rabbit.core.RabbitAdmin;
import org.springframework.dao.DataAccessException;
import org.springframework.data.domain.PageRequest;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;

import java.util.Map;

@Service
public class SubmissionMonitorService {

    private final SubmissionRepository submissionRepository;
    private final RabbitAdmin rabbitAdmin;

    public SubmissionMonitorService(SubmissionRepository submissionRepository, RabbitAdmin rabbitAdmin) {
        this.submissionRepository = submissionRepository;
        this.rabbitAdmin = rabbitAdmin;
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public PageResponse<SubmissionResponse> listSubmissions(int page, int size) {
        return PageResponse.from(
            submissionRepository.findAllByOrderBySubmittedAtDesc(PageRequest.of(page, size)),
            SubmissionResponse::from
        );
    }

    public Map<String, Integer> getQueueDepth() {
        int gradingDepth = getQueueMessageCount("grading-queue");
        int blueprintDepth = getQueueMessageCount("blueprint-queue");
        int codegenDepth = getQueueMessageCount("codegen-request-queue");
        return Map.of(
            "depth", gradingDepth,
            "grading-queue", gradingDepth,
            "blueprint-queue", blueprintDepth,
            "codegen-request-queue", codegenDepth
        );
    }

    private int getQueueMessageCount(String queueName) {
        try {
            var info = rabbitAdmin.getQueueInfo(queueName);
            return info != null ? info.getMessageCount() : 0;
        } catch (Exception e) {
            return -1;
        }
    }
}
