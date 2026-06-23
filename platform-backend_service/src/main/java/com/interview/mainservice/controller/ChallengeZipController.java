package com.interview.mainservice.controller;

import com.interview.mainservice.model.Problem;
import com.interview.mainservice.repository.ProblemRepository;
import io.minio.GetObjectArgs;
import io.minio.MinioClient;
import java.io.InputStream;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

@RestController
@RequestMapping("/api/v1/problems")
public class ChallengeZipController {

    private final ProblemRepository problemRepository;
    private final MinioClient minioClient;

    @Value("${app.minio.challenges-bucket:challenges}")
    private String challengesBucket;

    public ChallengeZipController(ProblemRepository problemRepository, MinioClient minioClient) {
        this.problemRepository = problemRepository;
        this.minioClient = minioClient;
    }

    @GetMapping("/{id}/zip")
    public ResponseEntity<StreamingResponseBody> getChallengeZip(@PathVariable UUID id) {
        Problem problem = problemRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Problem not found"));

        String language = problem.getLanguage();
        if (language == null || problem.getSlug() == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND,
                    "Challenge ZIP not available — problem missing language or slug");
        }

        // Slug already encodes the full path: {challenge}-{scenario_key}
        // e.g. "vending-machine-system-easy-restock-product"
        // Codegen stores ZIPs as: {language}/{challenge}-{scenario_key}.zip
        String s3Key = language + "/" + problem.getSlug() + ".zip";

        StreamingResponseBody body = out -> {
            try (InputStream stream = minioClient.getObject(
                    GetObjectArgs.builder().bucket(challengesBucket).object(s3Key).build())) {
                stream.transferTo(out);
            } catch (Exception e) {
                throw new RuntimeException("Failed to stream ZIP from storage: " + e.getMessage(), e);
            }
        };

        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_OCTET_STREAM_VALUE)
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"challenge.zip\"")
                .header("Cross-Origin-Resource-Policy", "cross-origin")
                .body(body);
    }
}
