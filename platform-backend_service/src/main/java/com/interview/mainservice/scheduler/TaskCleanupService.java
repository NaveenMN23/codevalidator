package com.interview.mainservice.scheduler;

import com.interview.mainservice.repository.SessionRepository;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.services.ecs.EcsClient;
import software.amazon.awssdk.services.ecs.model.DescribeTasksRequest;
import software.amazon.awssdk.services.ecs.model.DescribeTasksResponse;
import software.amazon.awssdk.services.ecs.model.DesiredStatus;
import software.amazon.awssdk.services.ecs.model.ListTasksRequest;
import software.amazon.awssdk.services.ecs.model.ListTasksResponse;
import software.amazon.awssdk.services.ecs.model.StopTaskRequest;
import software.amazon.awssdk.services.ecs.model.Task;

@Component
public class TaskCleanupService {

    private static final Logger log = LoggerFactory.getLogger(TaskCleanupService.class);

    // A task becomes visible to ECS's listTasks(desiredStatus=RUNNING) the instant runTask()
    // returns, but is only recorded in Redis on the next line of ExecutionService.doSpawn().
    // That gap isn't atomic, so never treat a freshly-created task as orphaned regardless of
    // what Redis shows for it yet.
    private static final Duration MIN_TASK_AGE_BEFORE_CLEANUP = Duration.ofMinutes(3);

    private final EcsClient ecsClient;
    private final SessionRepository sessionRepository;

    @Value("${app.aws.ecs.cluster-arn}")
    private String clusterArn;

    public TaskCleanupService(EcsClient ecsClient, SessionRepository sessionRepository) {
        this.ecsClient = ecsClient;
        this.sessionRepository = sessionRepository;
    }

    @Scheduled(fixedDelay = 120_000)
    public void stopOrphanedTasks() {
        if (clusterArn == null || clusterArn.isBlank()) {
            log.warn("Skipping orphaned ECS task cleanup: app.aws.ecs.cluster-arn is not configured");
            return;
        }

        Set<String> activeTaskArns = sessionRepository.getActiveTaskArns();

        List<String> candidateArns = new ArrayList<>();
        String nextToken = null;
        do {
            ListTasksResponse response = ecsClient.listTasks(ListTasksRequest.builder()
                    .cluster(clusterArn)
                    .desiredStatus(DesiredStatus.RUNNING)
                    .nextToken(nextToken)
                    .build());

            for (String taskArn : response.taskArns()) {
                if (!activeTaskArns.contains(taskArn)) {
                    candidateArns.add(taskArn);
                }
            }

            nextToken = response.nextToken();
        } while (nextToken != null);

        if (candidateArns.isEmpty()) {
            return;
        }

        Instant cutoff = Instant.now().minus(MIN_TASK_AGE_BEFORE_CLEANUP);

        // DescribeTasks accepts at most 100 task ARNs per call.
        for (int i = 0; i < candidateArns.size(); i += 100) {
            List<String> batch = candidateArns.subList(i, Math.min(i + 100, candidateArns.size()));
            DescribeTasksResponse described = ecsClient.describeTasks(DescribeTasksRequest.builder()
                    .cluster(clusterArn)
                    .tasks(batch)
                    .build());

            for (Task task : described.tasks()) {
                if (task.createdAt() != null && task.createdAt().isAfter(cutoff)) {
                    log.debug("Skipping cleanup for task {}: created too recently ({})",
                            task.taskArn(), task.createdAt());
                    continue;
                }
                try {
                    log.info("Stopping orphaned ECS task: {}", task.taskArn());
                    ecsClient.stopTask(StopTaskRequest.builder()
                            .cluster(clusterArn)
                            .task(task.taskArn())
                            .reason("Session expired")
                            .build());
                } catch (Exception e) {
                    log.warn("Failed to stop orphaned task {}: {}", task.taskArn(), e.getMessage());
                }
            }
        }
    }
}
