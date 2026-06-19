package com.interview.platform.service;

import com.interview.platform.config.RabbitMQConfig;
import com.interview.platform.dto.GradingResult;
import com.interview.platform.model.Submission;
import com.interview.platform.repository.SubmissionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class GradingResultListener {

    private final SubmissionRepository submissionRepository;

    @Transactional
    @RabbitListener(queues = RabbitMQConfig.GRADING_RESULTS_QUEUE)
    public void handleGradingResult(GradingResult result) {
        log.info("Received grading result for submission {}: status {}", result.getSubmissionId(), result.getStatus());
        
        submissionRepository.findById(result.getSubmissionId()).ifPresent(submission -> {
            submission.setStatus(result.getStatus());
            submission.setScore(result.getScore() != null ? result.getScore() : 0);
            
            // When errorOutput is empty, output is a refined one-at-a-time failure message
            // (e.g. "❌ Failed: ...") — use it directly without boilerplate wrapping.
            // For system errors and timeouts, errorOutput is present, so use the full format.
            String errorOut = result.getErrorOutput() != null ? result.getErrorOutput() : "";
            String formattedLogs;
            if (errorOut.isBlank()) {
                formattedLogs = result.getOutput() != null ? result.getOutput() : "";
            } else {
                formattedLogs = String.format("Exit Code: %d\n\n--- Standard Output ---\n%s\n\n--- Error Output ---\n%s",
                        result.getExitCode(),
                        result.getOutput() != null ? result.getOutput() : "",
                        errorOut);
            }

            submission.setLogs(formattedLogs);
            
            // Save AI feedback if present
            if (result.getFeedback() != null) {
                submission.setFeedback(result.getFeedback());
            }
            
            submissionRepository.save(submission);
            log.info("Successfully updated submission {}", submission.getId());
        });
    }
}
