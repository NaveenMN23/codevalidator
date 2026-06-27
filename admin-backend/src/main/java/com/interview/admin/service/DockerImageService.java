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

@Service
public class DockerImageService {

    private static final Logger log = LoggerFactory.getLogger(DockerImageService.class);

    private final S3Client s3Client;
    private final EcrClient ecrClient;

    @Value("${app.aws.s3.challenges-bucket:challenges-repo}")
    private String challengesBucket;

    @Value("${app.aws.ecr.repository-uri:}")
    private String ecrRepositoryUri;

    public DockerImageService(S3Client s3Client, EcrClient ecrClient) {
        this.s3Client = s3Client;
        this.ecrClient = ecrClient;
    }

    /**
     * Downloads scaffold ZIP from S3, extracts the language dependency file, builds a
     * per-challenge Docker image, and pushes it to ECR. Runs asynchronously so it never
     * blocks the RabbitMQ listener. If ECR_REPOSITORY_URI is not configured, the image
     * is stored locally only.
     */
    @Async
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

            Files.writeString(tmpDir.resolve("Dockerfile"), DockerfileTemplates.build(language, depFile != null));

            log.info("Building Docker image {} from scaffold {}", localTag, s3Key);
            runCommand(tmpDir, "docker", "build", "-t", localTag, ".");
            log.info("Docker image {} built successfully", localTag);

            if (ecrRepositoryUri == null || ecrRepositoryUri.isBlank()) {
                log.warn("ECR_REPOSITORY_URI not configured — image {} stored locally only", localTag);
                return;
            }

            String ecrTag = ecrRepositoryUri + ":" + slug;
            String registry = ecrRepositoryUri.substring(0, ecrRepositoryUri.indexOf("/"));

            authenticateDockerToEcr(registry);
            runCommand(null, "docker", "tag", localTag, ecrTag);
            runCommand(null, "docker", "push", ecrTag);
            log.info("Pushed {} to ECR", ecrTag);

        } catch (Exception e) {
            log.error("Failed to build/push Docker image for slug {}: {}", slug, e.getMessage(), e);
        } finally {
            deleteTempDir(tmpDir);
        }
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
