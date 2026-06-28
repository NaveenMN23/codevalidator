package com.interview.mainservice.infrastructure;

import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;

@Service
public class ChallengeStorageService {

    private static final Logger log = LoggerFactory.getLogger(ChallengeStorageService.class);

    private final S3Client s3Client;

    @Value("${app.aws.s3.challenges-bucket}")
    private String challengesBucket;

    public ChallengeStorageService(S3Client s3Client) {
        this.s3Client = s3Client;
    }

    @CircuitBreaker(name = "storage")
    public Map<String, String> fetchFiles(UUID problemId, String s3Key) {
        if (s3Key == null || s3Key.isBlank()) {
            return Map.of();
        }

        Map<String, String> files = new LinkedHashMap<>();
        try (InputStream stream = s3Client.getObject(
                GetObjectRequest.builder().bucket(challengesBucket).key(s3Key).build());
             ZipInputStream zip = new ZipInputStream(stream)) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (!entry.isDirectory()) {
                    files.put(entry.getName(), new String(zip.readAllBytes()));
                }
            }
        } catch (Exception e) {
            log.error("Failed to fetch challenge files for problem {} (bucket={}, key={}): {}",
                    problemId, challengesBucket, s3Key, e.getMessage());
            throw new ResponseStatusException(HttpStatus.NOT_FOUND,
                    "Challenge files not available — failed to read from storage: " + e.getMessage());
        }
        return files;
    }
}
