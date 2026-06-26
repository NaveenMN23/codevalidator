package com.interview.mainservice.service;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.dto.RunResponse;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.services.ecs.EcsClient;
import software.amazon.awssdk.services.ecs.model.AssignPublicIp;
import software.amazon.awssdk.services.ecs.model.KeyValuePair;
import software.amazon.awssdk.services.ecs.model.AwsVpcConfiguration;
import software.amazon.awssdk.services.ecs.model.ContainerOverride;
import software.amazon.awssdk.services.ecs.model.DescribeTasksRequest;
import software.amazon.awssdk.services.ecs.model.DescribeTasksResponse;
import software.amazon.awssdk.services.ecs.model.LaunchType;
import software.amazon.awssdk.services.ecs.model.NetworkConfiguration;
import software.amazon.awssdk.services.ecs.model.RunTaskRequest;
import software.amazon.awssdk.services.ecs.model.RunTaskResponse;
import software.amazon.awssdk.services.ecs.model.Task;
import software.amazon.awssdk.services.ecs.model.TaskOverride;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;

@Service
public class ExecutionService {

    private static final int TASK_START_POLL_INTERVAL_MS = 3_000;
    private static final int TASK_START_TIMEOUT_MS = 90_000;

    private final EcsClient ecsClient;
    private final S3Client s3Client;
    private final RedisSessionStore sessionStore;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;

    @Value("${app.aws.ecs.cluster-arn}")
    private String clusterArn;

    @Value("${app.aws.ecs.subnet-ids}")
    private String subnetIds;

    @Value("${app.aws.ecs.security-group-id}")
    private String securityGroupId;

    @Value("${app.aws.s3.gold-masters-bucket}")
    private String goldMastersBucket;

    @Value("${app.fargate.session-ttl-seconds}")
    private long sessionTtlSeconds;

    @Value("${app.fargate.sandbox-server-port}")
    private int sandboxServerPort;

    public ExecutionService(EcsClient ecsClient, S3Client s3Client,
                            RedisSessionStore sessionStore, ObjectMapper objectMapper) {
        this.ecsClient = ecsClient;
        this.s3Client = s3Client;
        this.sessionStore = sessionStore;
        this.objectMapper = objectMapper;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
    }

    public RunResponse execute(String sessionId, String ecrImageUri, Map<String, String> files, String command) {
        String privateIp = getOrSpawnTask(sessionId, ecrImageUri);
        RunResponse response = forwardToSandbox(privateIp, files, command);
        sessionStore.refreshTtl(sessionId, sessionTtlSeconds);
        return response;
    }

    public RunResponse submit(String sessionId, String ecrImageUri, String challengeSlug,
                              String language, Map<String, String> files, String command) {
        String privateIp = getOrSpawnTask(sessionId, ecrImageUri);

        HiddenTestResult hiddenTest = fetchHiddenTest(challengeSlug, language);
        Map<String, String> allFiles = new HashMap<>(files);
        allFiles.putAll(hiddenTest.lockedFiles());
        allFiles.put(hiddenTest.hiddenTestPath(), hiddenTest.hiddenTestContent());

        RunResponse response = forwardToSandbox(privateIp, allFiles, command);
        sessionStore.refreshTtl(sessionId, sessionTtlSeconds);
        return response;
    }

    private String getOrSpawnTask(String sessionId, String ecrImageUri) {
        return sessionStore.getSession(sessionId)
                .map(RedisSessionStore.SessionEntry::privateIp)
                .orElseGet(() -> spawnAndRegister(sessionId, ecrImageUri));
    }

    private String spawnAndRegister(String sessionId, String ecrImageUri) {
        List<String> subnets = Arrays.asList(subnetIds.split(","));

        RunTaskRequest runTaskRequest = RunTaskRequest.builder()
                .cluster(clusterArn)
                .launchType(LaunchType.FARGATE)
                .networkConfiguration(NetworkConfiguration.builder()
                        .awsvpcConfiguration(AwsVpcConfiguration.builder()
                                .subnets(subnets)
                                .securityGroups(securityGroupId)
                                .assignPublicIp(AssignPublicIp.DISABLED)
                                .build())
                        .build())
                .overrides(TaskOverride.builder()
                        .containerOverrides(ContainerOverride.builder()
                                .name("sandbox")
                                .build())
                        .build())
                .build();

        RunTaskResponse runTaskResponse = ecsClient.runTask(runTaskRequest);
        if (runTaskResponse.tasks().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Failed to start execution container");
        }

        Task task = runTaskResponse.tasks().get(0);
        String taskArn = task.taskArn();
        String privateIp = waitForTaskRunning(taskArn);

        sessionStore.setSession(sessionId, privateIp, taskArn, sessionTtlSeconds);
        return privateIp;
    }

    private String waitForTaskRunning(String taskArn) {
        long deadline = System.currentTimeMillis() + TASK_START_TIMEOUT_MS;

        while (System.currentTimeMillis() < deadline) {
            DescribeTasksResponse describeResponse = ecsClient.describeTasks(
                    DescribeTasksRequest.builder()
                            .cluster(clusterArn)
                            .tasks(taskArn)
                            .build());

            if (!describeResponse.tasks().isEmpty()) {
                Task task = describeResponse.tasks().get(0);
                if ("RUNNING".equals(task.lastStatus())) {
                    return extractPrivateIp(task);
                }
                if ("STOPPED".equals(task.lastStatus())) {
                    throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                            "Execution container stopped unexpectedly: " + task.stoppedReason());
                }
            }

            try {
                Thread.sleep(TASK_START_POLL_INTERVAL_MS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Interrupted while waiting for container");
            }
        }

        throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Timed out waiting for execution container to start");
    }

    private String extractPrivateIp(Task task) {
        return task.attachments().stream()
                .filter(a -> "ElasticNetworkInterface".equals(a.type()))
                .findFirst()
                .flatMap(a -> a.details().stream()
                        .filter(d -> "privateIPv4Address".equals(d.name()))
                        .findFirst())
                .map(KeyValuePair::value)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                        "Could not determine container IP address"));
    }

    private RunResponse forwardToSandbox(String privateIp, Map<String, String> files, String command) {
        SandboxRequest body = new SandboxRequest(files, command);
        try {
            String json = objectMapper.writeValueAsString(body);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("http://" + privateIp + ":" + sandboxServerPort + "/execute"))
                    .timeout(Duration.ofSeconds(90))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                return new RunResponse(false, "", "Sandbox returned HTTP " + response.statusCode(), -1);
            }

            SandboxResponse parsed = objectMapper.readValue(response.body(), SandboxResponse.class);
            return new RunResponse(parsed.success(), parsed.stdout(), parsed.stderr(), parsed.exitCode());
        } catch (IOException | InterruptedException e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            return new RunResponse(false, "", "Failed to reach execution container: " + e.getMessage(), -1);
        }
    }

    private HiddenTestResult fetchHiddenTest(String challengeSlug, String language) {
        String s3Key = language + "/" + challengeSlug + ".zip";
        ResponseBytes<GetObjectResponse> responseBytes = s3Client.getObjectAsBytes(
                GetObjectRequest.builder()
                        .bucket(goldMastersBucket)
                        .key(s3Key)
                        .build());

        Map<String, String> lockedFiles = new HashMap<>();
        String hiddenTestPath = null;
        String hiddenTestContent = null;

        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(responseBytes.asByteArray()))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) continue;
                String name = entry.getName();
                String content = new String(zip.readAllBytes());

                if (name.startsWith("src/")) {
                    lockedFiles.put(name, content);
                } else if (name.startsWith("test-hidden/") && hiddenTestContent == null) {
                    hiddenTestContent = content;
                    hiddenTestPath = resolveHiddenTestPath(content, language);
                }
                zip.closeEntry();
            }
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "Failed to fetch hidden test for: " + challengeSlug);
        }

        if (hiddenTestContent == null) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "No hidden test found for: " + challengeSlug);
        }

        return new HiddenTestResult(lockedFiles, hiddenTestPath, hiddenTestContent);
    }

    private String resolveHiddenTestPath(String content, String language) {
        if (!"java".equals(language)) return "test-hidden/HiddenTest." + language;

        String packageName = "";
        String className = "HiddenTest";

        for (String line : content.split("\n")) {
            String trimmed = line.trim();
            if (trimmed.startsWith("package ")) {
                packageName = trimmed.substring("package ".length()).replace(";", "").trim();
            } else if (trimmed.startsWith("public class ") || trimmed.startsWith("class ")) {
                String[] parts = trimmed.split("\\s+");
                for (int i = 0; i < parts.length - 1; i++) {
                    if ("class".equals(parts[i])) {
                        className = parts[i + 1].split("[{<]")[0];
                        break;
                    }
                }
            }
        }

        String packagePath = packageName.replace('.', '/');
        return "src/test/java/" + (packagePath.isEmpty() ? "" : packagePath + "/") + className + ".java";
    }

    private record SandboxRequest(Map<String, String> files, String command) {}

    private record SandboxResponse(boolean success, String stdout, String stderr,
                                   @JsonProperty("exit_code") int exitCode) {}

    public record HiddenTestResult(Map<String, String> lockedFiles, String hiddenTestPath, String hiddenTestContent) {}
}
