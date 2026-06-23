package com.interview.mainservice.config;

import io.minio.MinioClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MinioConfig {

    @Value("${app.minio.endpoint:http://localhost:9000}")
    private String endpoint;

    @Value("${app.minio.access-key:admin}")
    private String accessKey;

    @Value("${app.minio.secret-key:password}")
    private String secretKey;

    @Bean
    public MinioClient minioClient() {
        return MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
    }
}
