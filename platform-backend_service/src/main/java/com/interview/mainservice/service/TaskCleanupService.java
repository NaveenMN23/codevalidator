package com.interview.mainservice.service;

import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.ecs.EcsClient;
import software.amazon.awssdk.services.ecs.model.DesiredStatus;
import software.amazon.awssdk.services.ecs.model.ListTasksRequest;
import software.amazon.awssdk.services.ecs.model.ListTasksResponse;
import software.amazon.awssdk.services.ecs.model.StopTaskRequest;

@Service
public class TaskCleanupService {

    private static final Logger log = LoggerFactory.getLogger(TaskCleanupService.class);

    private final EcsClient ecsClient;
    private final RedisSessionStore sessionStore;

    @Value("${app.aws.ecs.cluster-arn}")
    private String clusterArn;

    public TaskCleanupService(EcsClient ecsClient, RedisSessionStore sessionStore) {
        this.ecsClient = ecsClient;
        this.sessionStore = sessionStore;
    }

    @Scheduled(fixedDelay = 120_000)
    public void stopOrphanedTasks() {
        Set<String> activeTaskArns = sessionStore.getActiveTaskArns();

        String nextToken = null;
        do {
            ListTasksResponse response = ecsClient.listTasks(ListTasksRequest.builder()
                    .cluster(clusterArn)
                    .desiredStatus(DesiredStatus.RUNNING)
                    .nextToken(nextToken)
                    .build());

            for (String taskArn : response.taskArns()) {
                if (!activeTaskArns.contains(taskArn)) {
                    log.info("Stopping orphaned ECS task: {}", taskArn);
                    ecsClient.stopTask(StopTaskRequest.builder()
                            .cluster(clusterArn)
                            .task(taskArn)
                            .reason("Session expired")
                            .build());
                }
            }

            nextToken = response.nextToken();
        } while (nextToken != null);
    }
}
