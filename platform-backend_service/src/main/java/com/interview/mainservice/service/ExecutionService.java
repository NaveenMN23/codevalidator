package com.interview.mainservice.service;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.dto.RunResponse;
import com.interview.mainservice.dto.TestCaseResult;
import com.interview.mainservice.infrastructure.ChallengeStorageService;
import com.interview.mainservice.repository.SessionRepository;
import com.interview.mainservice.testreport.JUnitXmlReportParser;
import com.interview.mainservice.testreport.ReportFile;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ExecutorService;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.services.ec2.Ec2Client;
import software.amazon.awssdk.services.ec2.model.DescribeNetworkInterfacesRequest;
import software.amazon.awssdk.services.ec2.model.NetworkInterface;
import software.amazon.awssdk.services.ecs.EcsClient;
import software.amazon.awssdk.services.ecs.model.AssignPublicIp;
import software.amazon.awssdk.services.ecs.model.KeyValuePair;
import software.amazon.awssdk.services.ecs.model.AwsVpcConfiguration;
import software.amazon.awssdk.services.ecs.model.ClientException;
import software.amazon.awssdk.services.ecs.model.Compatibility;
import software.amazon.awssdk.services.ecs.model.ContainerDefinition;
import software.amazon.awssdk.services.ecs.model.ContainerOverride;
import software.amazon.awssdk.services.ecs.model.DescribeTaskDefinitionRequest;
import software.amazon.awssdk.services.ecs.model.DescribeTasksRequest;
import software.amazon.awssdk.services.ecs.model.DescribeTasksResponse;
import software.amazon.awssdk.services.ecs.model.LaunchType;
import software.amazon.awssdk.services.ecs.model.LogConfiguration;
import software.amazon.awssdk.services.ecs.model.LogDriver;
import software.amazon.awssdk.services.ecs.model.NetworkConfiguration;
import software.amazon.awssdk.services.ecs.model.NetworkMode;
import software.amazon.awssdk.services.ecs.model.PortMapping;
import software.amazon.awssdk.services.ecs.model.RegisterTaskDefinitionRequest;
import software.amazon.awssdk.services.ecs.model.RunTaskRequest;
import software.amazon.awssdk.services.ecs.model.RunTaskResponse;
import software.amazon.awssdk.services.ecs.model.Task;
import software.amazon.awssdk.services.ecs.model.TaskOverride;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;

@Service
public class ExecutionService {

    private static final Logger log = LoggerFactory.getLogger(ExecutionService.class);

    private static final int TASK_START_POLL_INTERVAL_MS = 3_000;
    private static final int TASK_START_TIMEOUT_MS = 90_000;
    private static final int SPAWN_LOCK_TTL_SECONDS = 100;
    private static final Duration SESSION_HEALTH_CHECK_TIMEOUT = Duration.ofSeconds(2);

    private static final Map<String, String> LANGUAGE_COMMANDS = Map.of(
            "java",   "mvn -o test -Dsurefire.skipAfterFailureCount=1",
            "node",   "npm test",
            "python", "pytest"
    );

    public static String resolveCommand(String language) {
        String command = LANGUAGE_COMMANDS.get(language);
        if (command == null) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Unsupported language: " + language);
        }
        return command;
    }

    private final EcsClient ecsClient;
    private final Ec2Client ec2Client;
    private final S3Client s3Client;
    private final SessionRepository sessionStore;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;
    private final ExecutorService executionServiceExecutor;

    @Value("${app.aws.ecs.cluster-arn}")
    private String clusterArn;

    @Value("${app.aws.ecs.subnet-ids}")
    private String subnetIds;

    @Value("${app.aws.ecs.security-group-id}")
    private String securityGroupId;

    @Value("${app.aws.ecs.execution-role-arn}")
    private String executionRoleArn;

    @Value("${app.aws.ecs.assign-public-ip:DISABLED}")
    private AssignPublicIp assignPublicIp;

    @Value("${AWS_REGION:ap-southeast-2}")
    private String awsRegion;

    @Value("${app.aws.s3.gold-masters-bucket}")
    private String goldMastersBucket;

    @Value("${app.fargate.session-ttl-seconds}")
    private long sessionTtlSeconds;

    @Value("${app.fargate.sandbox-server-port}")
    private int sandboxServerPort;

    public ExecutionService(EcsClient ecsClient, Ec2Client ec2Client, S3Client s3Client,
                            SessionRepository sessionStore, ObjectMapper objectMapper,
                            ExecutorService executionServiceExecutor) {
        this.ecsClient = ecsClient;
        this.ec2Client = ec2Client;
        this.s3Client = s3Client;
        this.sessionStore = sessionStore;
        this.objectMapper = objectMapper;
        this.executionServiceExecutor = executionServiceExecutor;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
    }

    public RunResponse execute(String sessionId, String ecrImageUri, String language, Map<String, String> files,
                               String command) {
        String privateIp = getOrSpawnTask(sessionId, ecrImageUri);
        RunResponse response = forwardToSandbox(sessionId, privateIp, language, files, command);
        sessionStore.refreshTtl(sessionId, sessionTtlSeconds);
        return response;
    }

    public RunResponse submit(String sessionId, String ecrImageUri, String hiddenTestKey,
                              String language, Map<String, String> files, String command) {
        String privateIp = getOrSpawnTask(sessionId, ecrImageUri);

        HiddenTestResult hiddenTest = fetchHiddenTest(hiddenTestKey, language);
        // Gold-master src/ files are a fallback for anything the candidate's submission
        // is missing (e.g. a supporting class the hidden test needs to compile) — the
        // candidate's own files must win on any path collision, or we'd grade our own
        // reference solution instead of what they wrote.
        Map<String, String> allFiles = new HashMap<>(hiddenTest.referenceFiles());
        allFiles.putAll(files);
        allFiles.put(hiddenTest.hiddenTestPath(), hiddenTest.hiddenTestContent());

        RunResponse response = forwardToSandbox(sessionId, privateIp, language, allFiles, command);
        sessionStore.refreshTtl(sessionId, sessionTtlSeconds);
        return response;
    }

    /**
     * Eagerly starts a Fargate task for this session without blocking the caller — the spawn
     * runs on {@code executionServiceExecutor} so a problem-open request can return immediately
     * while the ~30-60s cold start happens in the background.
     */
    public void warmUp(String sessionId, String ecrImageUri) {
        executionServiceExecutor.submit(() -> {
            try {
                Optional<SessionRepository.SessionEntry> existing = sessionStore.getSession(sessionId);
                if (existing.isPresent()) {
                    if (isSessionAlive(existing.get())) {
                        return;
                    }
                    log.info("Discarding stale session {} (failed health check), respawning", sessionId);
                    sessionStore.deleteSession(sessionId);
                }
                spawnAndRegister(sessionId, ecrImageUri);
            } catch (Exception e) {
                log.warn("Warm-up spawn failed for session {}: {}", sessionId, e.getMessage());
            }
        });
    }

    private String getOrSpawnTask(String sessionId, String ecrImageUri) {
        Optional<SessionRepository.SessionEntry> existing = sessionStore.getSession(sessionId);
        if (existing.isPresent()) {
            if (isSessionAlive(existing.get())) {
                return existing.get().privateIp();
            }
            log.info("Discarding stale session {} (failed health check), respawning", sessionId);
            sessionStore.deleteSession(sessionId);
        }
        return spawnAndRegister(sessionId, ecrImageUri);
    }

    // A cached session's privateIp can point at a task that already died (killed by cleanup,
    // crashed, reclaimed) while its Redis record is still within TTL. Trusting that record
    // blindly means warmUp() silently no-ops forever (a 202 that starts nothing), and a real
    // Run hangs until forwardToSandbox's own retry+evict kicks in minutes later. This fast
    // probe catches a dead session immediately instead.
    private boolean isSessionAlive(SessionRepository.SessionEntry session) {
        try {
            HttpRequest healthRequest = HttpRequest.newBuilder()
                    .uri(URI.create("http://" + session.privateIp() + ":" + sandboxServerPort + "/health"))
                    .timeout(SESSION_HEALTH_CHECK_TIMEOUT)
                    .GET()
                    .build();
            HttpResponse<Void> response = httpClient.send(healthRequest, HttpResponse.BodyHandlers.discarding());
            return response.statusCode() == 200;
        } catch (IOException e) {
            return false;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    /**
     * Holds a short-lived Redis lock around the actual spawn so a /run call racing an
     * in-flight warm-up (or two concurrent callers) doesn't start two Fargate tasks for the
     * same session — the loser waits for the winner's session to appear instead.
     */
    private String spawnAndRegister(String sessionId, String ecrImageUri) {
        if (!sessionStore.tryMarkSpawning(sessionId, SPAWN_LOCK_TTL_SECONDS)) {
            return awaitInFlightSpawn(sessionId);
        }
        try {
            return doSpawn(sessionId, ecrImageUri);
        } finally {
            sessionStore.clearSpawning(sessionId);
        }
    }

    private String doSpawn(String sessionId, String ecrImageUri) {
        List<String> subnets = Arrays.asList(subnetIds.split(","));
        String taskDefinition = resolveTaskDefinition(ecrImageUri);

        RunTaskRequest runTaskRequest = RunTaskRequest.builder()
                .cluster(clusterArn)
                .taskDefinition(taskDefinition)
                .launchType(LaunchType.FARGATE)
                .networkConfiguration(NetworkConfiguration.builder()
                        .awsvpcConfiguration(AwsVpcConfiguration.builder()
                                .subnets(subnets)
                                .securityGroups(securityGroupId)
                                .assignPublicIp(assignPublicIp)
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
        sessionStore.updateSpawningArn(sessionId, taskArn, SPAWN_LOCK_TTL_SECONDS);
        String privateIp = waitForTaskRunning(taskArn);

        sessionStore.setSession(sessionId, privateIp, taskArn, sessionTtlSeconds);
        return privateIp;
    }

    /**
     * Resolves the task definition family whose container image is {@code ecrImageUri},
     * registering it on first use. ECS has no way to override a container's image at RunTask
     * time, so each distinct ECR image needs its own task definition; the family name is a
     * stable hash of the image URI so repeated calls for the same image reuse it.
     */
    private String resolveTaskDefinition(String ecrImageUri) {
        String family = "sandbox-" + sha256Hex(ecrImageUri).substring(0, 16);
        try {
            ecsClient.describeTaskDefinition(DescribeTaskDefinitionRequest.builder()
                    .taskDefinition(family)
                    .build());
            return family;
        } catch (ClientException e) {
            ecsClient.registerTaskDefinition(RegisterTaskDefinitionRequest.builder()
                    .family(family)
                    .networkMode(NetworkMode.AWSVPC)
                    .requiresCompatibilities(Compatibility.FARGATE)
                    .cpu("512")
                    .memory("1024")
                    .executionRoleArn(executionRoleArn)
                    .containerDefinitions(ContainerDefinition.builder()
                            .name("sandbox")
                            .image(ecrImageUri)
                            .portMappings(PortMapping.builder().containerPort(sandboxServerPort).build())
                            .logConfiguration(LogConfiguration.builder()
                                    .logDriver(LogDriver.AWSLOGS)
                                    .options(Map.of(
                                            "awslogs-group", "/ecs/sandbox",
                                            "awslogs-region", awsRegion,
                                            "awslogs-stream-prefix", "sandbox",
                                            "awslogs-create-group", "true"))
                                    .build())
                            .build())
                    .build());
            return family;
        }
    }

    private String sha256Hex(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }

    private String awaitInFlightSpawn(String sessionId) {
        long deadline = System.currentTimeMillis() + TASK_START_TIMEOUT_MS;
        while (System.currentTimeMillis() < deadline) {
            Optional<SessionRepository.SessionEntry> session = sessionStore.getSession(sessionId);
            if (session.isPresent()) {
                return session.get().privateIp();
            }
            sleepPoll();
        }
        throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                "Timed out waiting for in-flight container spawn");
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

            sleepPoll();
        }

        throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Timed out waiting for execution container to start");
    }

    private void sleepPoll() {
        try {
            Thread.sleep(TASK_START_POLL_INTERVAL_MS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Interrupted while waiting for container");
        }
    }

    private String extractPrivateIp(Task task) {
        var eni = task.attachments().stream()
                .filter(a -> "ElasticNetworkInterface".equals(a.type()))
                .findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                        "Could not determine container IP address"));

        if (assignPublicIp == AssignPublicIp.ENABLED) {
            String eniId = eni.details().stream()
                    .filter(d -> "networkInterfaceId".equals(d.name()))
                    .map(KeyValuePair::value)
                    .findFirst()
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                            "Could not find ENI ID in task attachment"));

            NetworkInterface ni = ec2Client.describeNetworkInterfaces(
                    DescribeNetworkInterfacesRequest.builder()
                            .networkInterfaceIds(eniId)
                            .build())
                    .networkInterfaces().stream()
                    .findFirst()
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                            "Could not resolve network interface: " + eniId));

            String publicIp = ni.association() != null ? ni.association().publicIp() : null;
            if (publicIp == null || publicIp.isBlank()) {
                throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                        "No public IP attached to ENI: " + eniId);
            }
            log.debug("Resolved public IP {} for ENI {} (task {})", publicIp, eniId, task.taskArn());
            return publicIp;
        }

        return eni.details().stream()
                .filter(d -> "privateIPv4Address".equals(d.name()))
                .map(KeyValuePair::value)
                .findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                        "Could not determine container IP address"));
    }

    // ECS reassigns a stopped task's private IP to a new task fairly quickly. The JDK
    // HttpClient's connection pool is keyed on host:port, so it can hand back a keep-alive
    // connection that was opened to a now-dead task at that same IP — the write succeeds
    // locally but nothing ever answers, and the call hangs until it times out. Connection:
    // close stops the client from pooling these connections at all, and a single retry with
    // a fresh connection covers any one-off failure that isn't actually about the task being
    // dead, so a single hiccup no longer throws away an otherwise-healthy warm session.
    private static final int SANDBOX_REQUEST_ATTEMPTS = 2;

    private RunResponse forwardToSandbox(String sessionId, String privateIp, String language,
                                         Map<String, String> files, String command) {
        SandboxRequest body = new SandboxRequest(files, command);
        String json;
        try {
            json = objectMapper.writeValueAsString(body);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Failed to serialize sandbox request", e);
        }

        Exception lastFailure = null;
        for (int attempt = 1; attempt <= SANDBOX_REQUEST_ATTEMPTS; attempt++) {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("http://" + privateIp + ":" + sandboxServerPort + "/execute"))
                    .timeout(Duration.ofSeconds(90))
                    .header("Content-Type", "application/json")
                    .header("Connection", "close")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();
            try {
                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
                if (response.statusCode() != 200) {
                    return new RunResponse(false, "", "Sandbox returned HTTP " + response.statusCode(), -1, List.of());
                }

                SandboxResponse parsed = objectMapper.readValue(response.body(), SandboxResponse.class);
                List<TestCaseResult> testResults = parsed.reportFiles() == null || parsed.reportFiles().isEmpty()
                        ? List.of()
                        : JUnitXmlReportParser.parse(parsed.reportFiles(), language);
                return new RunResponse(parsed.success(), parsed.stdout(), parsed.stderr(), parsed.exitCode(),
                        testResults);
            } catch (IOException e) {
                lastFailure = e;
                log.warn("Sandbox request to {} failed (attempt {}/{}) for session {}: {}",
                        privateIp, attempt, SANDBOX_REQUEST_ATTEMPTS, sessionId, e.toString());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return new RunResponse(false, "", "Failed to reach execution container: " + e.getMessage(), -1,
                        List.of());
            }
        }

        // Every attempt failed on its own fresh connection, so this isn't a stale pooled
        // connection — the task itself is genuinely unreachable. Evict the session so the
        // next request respawns instead of repeating this same failure until the TTL expires.
        log.warn("Evicting session {} after {} failed attempts to reach {}: {}",
                sessionId, SANDBOX_REQUEST_ATTEMPTS, privateIp, lastFailure);
        sessionStore.deleteSession(sessionId);
        return new RunResponse(false, "", "Failed to reach execution container: " + lastFailure.getMessage(), -1,
                List.of());
    }

    private HiddenTestResult fetchHiddenTest(String hiddenTestKey, String language) {
        ResponseBytes<GetObjectResponse> responseBytes = s3Client.getObjectAsBytes(
                GetObjectRequest.builder()
                        .bucket(goldMastersBucket)
                        .key(hiddenTestKey)
                        .build());

        Map<String, String> referenceFiles = new HashMap<>();
        String hiddenTestPath = null;
        String hiddenTestContent = null;

        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(responseBytes.asByteArray()))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) continue;
                String name = entry.getName();
                String content = new String(zip.readAllBytes());

                if (name.startsWith("src/")) {
                    referenceFiles.put(name, content);
                } else if (name.startsWith("test-hidden/") && hiddenTestContent == null) {
                    hiddenTestContent = content;
                    hiddenTestPath = resolveHiddenTestPath(content, language);
                }
                zip.closeEntry();
            }
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "Failed to fetch hidden test for key: " + hiddenTestKey);
        }

        if (hiddenTestContent == null) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "No hidden test found for key: " + hiddenTestKey);
        }

        return new HiddenTestResult(referenceFiles, hiddenTestPath, hiddenTestContent);
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
                                   @JsonProperty("exit_code") int exitCode,
                                   @JsonProperty("report_files") List<ReportFile> reportFiles) {}

    public record HiddenTestResult(Map<String, String> referenceFiles, String hiddenTestPath, String hiddenTestContent) {}
}
