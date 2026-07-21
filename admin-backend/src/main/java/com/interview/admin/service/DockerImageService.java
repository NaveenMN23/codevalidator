package com.interview.admin.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.services.ecr.EcrClient;
import software.amazon.awssdk.services.ecr.model.GetAuthorizationTokenResponse;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import org.springframework.retry.annotation.Retryable;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Recover;

import com.interview.admin.repository.ProblemRepository;
import com.interview.admin.model.Problem;

@Service
public class DockerImageService {

    private static final Logger log = LoggerFactory.getLogger(DockerImageService.class);

    private final S3Client s3Client;
    private final EcrClient ecrClient;
    private final ProblemRepository problemRepository;

    @Value("${app.aws.s3.challenges-bucket:challenges-repo}")
    private String challengesBucket;
    
    @Value("${app.aws.s3.gold-masters-bucket:gold-masters}")
    private String goldMastersBucket;

    @Value("${app.aws.ecr.repository-uri:}")
    private String ecrRepositoryUri;

    public DockerImageService(S3Client s3Client, EcrClient ecrClient, ProblemRepository problemRepository) {
        this.s3Client = s3Client;
        this.ecrClient = ecrClient;
        this.problemRepository = problemRepository;
    }

    public void deleteFromS3(String bucket, String s3Key) {
        try {
            s3Client.deleteObject(DeleteObjectRequest.builder().bucket(bucket).key(s3Key).build());
            log.info("Deleted object from S3: {}/{}", bucket, s3Key);
        } catch (Exception e) {
            log.error("Failed to delete object from S3 {}/{}: {}", bucket, s3Key, e.getMessage());
        }
    }

    /**
     * Downloads scaffold ZIP from S3, extracts the language dependency file, builds a
     * per-challenge Docker image, and pushes it to ECR. Runs asynchronously so it never
     * blocks the RabbitMQ listener. If ECR_REPOSITORY_URI is not configured, the image
     * is stored locally only.
     */
    @Async
    @Retryable(retryFor = Exception.class, maxAttempts = 3, backoff = @Backoff(delay = 5000, multiplier = 2.0))
    public void buildAndPush(String slug, String language, String s3Key) {
        if (!"java".equals(language) && !"python".equals(language) && !"node".equals(language)) {
            log.info("Skipping Docker image build for unsupported language '{}' (slug={})", language, slug);
            return;
        }

        String localTag = String.format("platform/%s-executor-%s:latest", language, slug);
        Path tmpDir = null;
        try {
            byte[] depFile = extractDependencyFileFromScaffoldZip(s3Key, language);
            tmpDir = Files.createTempDirectory("challenge-image-" + slug + "-");

            if (depFile != null) {
                Files.write(tmpDir.resolve(DockerfileTemplates.depFileName(language)), depFile);
            } else {
                log.warn("No dependency file found in scaffold ZIP {} for language {} — building plain image for {}", s3Key, language, slug);
            }

            // Extract the sandbox-runner binary from classpath and copy to tmpDir
            try (var is = getClass().getResourceAsStream("/sandbox-runner/sandbox-runner-bin")) {
                if (is == null) {
                    throw new RuntimeException("sandbox-runner-bin not found in classpath. Did you compile it?");
                }
                Path runnerPath = tmpDir.resolve("sandbox-runner-bin");
                Files.copy(is, runnerPath);
                runnerPath.toFile().setExecutable(true);
            }

            Files.writeString(tmpDir.resolve("Dockerfile"), DockerfileTemplates.build(language, depFile != null));

            log.info("Building Docker image {} from scaffold {}", localTag, s3Key);
            // Pin the target platform explicitly — AWS Fargate's default runtime is
            // linux/x86_64. Without this, `docker build` defaults to whatever
            // architecture the build machine itself runs (e.g. ARM64 on Apple Silicon),
            // producing an image Fargate can't execute at all: the container exits
            // immediately ("Essential container in task exited") since the entrypoint
            // binary is the wrong machine code for the runtime CPU.
            runCommand(tmpDir, "docker", "build", "--pull", "--platform", "linux/amd64", "-t", localTag, ".");
            log.info("Docker image {} built successfully", localTag);

            log.info("Validating Docker image {} — checking sandbox-runner health", localTag);
            // Match the build platform here too — on an ARM64 build host this now runs
            // the amd64 image under emulation, which is exactly what we want to validate
            // (the previous, unpinned version passed this same check while emulating
            // nothing, silently hiding the architecture mismatch that only surfaced once
            // deployed to Fargate's real x86_64 hardware).
            runCommand(null, "docker", "run", "--rm", "--platform", "linux/amd64", localTag, "/bin/sh", "-c",
                    "/usr/local/bin/sandbox-runner --port 8080 & sleep 4 && wget -qO- http://localhost:8080/health");
            log.info("Docker image {} passed sandbox-runner health check", localTag);

            if (ecrRepositoryUri == null || ecrRepositoryUri.isBlank()) {
                log.warn("ECR_REPOSITORY_URI not configured — image {} stored locally only", localTag);
                problemRepository.findBySlug(slug).ifPresent(p -> {
                    p.setPublished(true);
                    problemRepository.save(p);
                    log.info("Published problem '{}' after successful local build", slug);
                });
                return;
            }

            String ecrTag = ecrRepositoryUri + ":" + slug;
            String registry = ecrRepositoryUri.substring(0, ecrRepositoryUri.indexOf("/"));

            authenticateDockerToEcr(registry);
            runCommand(null, "docker", "tag", localTag, ecrTag);
            runCommand(null, "docker", "push", ecrTag);
            log.info("Pushed {} to ECR", ecrTag);

            final String finalEcrTag = ecrTag;
            problemRepository.findBySlug(slug).ifPresent(p -> {
                p.setEcrImageUri(finalEcrTag);
                p.setPublished(true);
                problemRepository.save(p);
                log.info("Published problem '{}' after successful image build", slug);
            });

        } catch (Exception e) {
            log.error("Failed to build/push Docker image for slug {}: {}", slug, e.getMessage(), e);
            throw new RuntimeException("Docker build/push failed", e);
        } finally {
            deleteTempDir(tmpDir);
        }
    }

    @Recover
    public void recoverBuildAndPush(Exception e, String slug, String language, String s3Key) {
        log.error("Ultimate failure: Docker build/push for {} failed after 3 retries. Rolling back.", slug);
        problemRepository.findBySlug(slug).ifPresent(p -> {
            problemRepository.delete(p);
            log.info("Rollback: Deleted problem '{}' from DB", slug);
        });
        
        // s3Key is like "language/challengeSlug.zip" or "language/challengeSlug-scenario.zip"
        deleteFromS3(challengesBucket, s3Key);
        
        // We also need to try to delete the gold master.
        // It's saved as "language/challengeSlug-tier.zip".
        // The exact key isn't perfectly identical to the challenge scenario in all cases,
        // but if it's identical, this will catch it. If not, it might leave an orphan in gold-masters.
        deleteFromS3(goldMastersBucket, s3Key);
    }

    private void authenticateDockerToEcr(String registry) throws IOException, InterruptedException {
        GetAuthorizationTokenResponse tokenResp = ecrClient.getAuthorizationToken();
        String encoded = tokenResp.authorizationData().get(0).authorizationToken();
        String decoded = new String(Base64.getDecoder().decode(encoded));
        String password = decoded.substring(decoded.indexOf(':') + 1);

        ProcessBuilder pb = new ProcessBuilder("docker", "login",
                "--username", "AWS",
                "--password-stdin",
                registry)
                .redirectErrorStream(true);
        Process proc = pb.start();
        proc.getOutputStream().write(password.getBytes());
        proc.getOutputStream().close();
        String output = new String(proc.getInputStream().readAllBytes());
        int exit = proc.waitFor();
        if (exit != 0) {
            throw new RuntimeException("docker login to ECR failed (exit " + exit + "):\n" + output);
        }
        log.info("Authenticated Docker to ECR registry {}", registry);
    }

    private void runCommand(Path workDir, String... cmd) throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder(cmd).redirectErrorStream(true);
        pb.environment().put("DOCKER_BUILDKIT", "1");
        if (workDir != null) pb.directory(workDir.toFile());
        Process proc = pb.start();
        String output = new String(proc.getInputStream().readAllBytes());
        int exit = proc.waitFor();
        if (exit != 0) {
            throw new RuntimeException(String.join(" ", cmd) + " failed (exit " + exit + "):\n" + output);
        }
        log.debug("{} output:\n{}", cmd[1], output);
    }

    private byte[] extractDependencyFileFromScaffoldZip(String s3Key, String language) throws IOException {
        String fileName = DockerfileTemplates.depFileName(language);
        
        GetObjectRequest req = GetObjectRequest.builder()
                .bucket(challengesBucket)
                .key(s3Key)
                .build();
        try (ResponseInputStream<GetObjectResponse> resp = s3Client.getObject(req);
             ZipInputStream zis = new ZipInputStream(resp)) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                if (entry.getName().endsWith(fileName)) {
                    return zis.readAllBytes();
                }
                zis.closeEntry();
            }
        }
        return null;
    }

    private void deleteTempDir(Path dir) {
        if (dir == null) return;
        try {
            try (var stream = Files.walk(dir)) {
                stream.sorted(java.util.Comparator.reverseOrder())
                      .map(Path::toFile)
                      .forEach(java.io.File::delete);
            }
        } catch (IOException e) {
            log.warn("Could not delete temp dir {}: {}", dir, e.getMessage());
        }
    }
}
