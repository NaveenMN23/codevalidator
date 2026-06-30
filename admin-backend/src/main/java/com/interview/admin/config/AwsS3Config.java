package com.interview.admin.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.ecr.EcrClient;
import software.amazon.awssdk.services.s3.S3Client;

@Configuration
public class AwsS3Config {

    @Value("${AWS_REGION:us-east-1}")
    private String region;

    @Value("${app.aws.ecr.repository-uri:}")
    private String ecrRepositoryUri;

    @Bean
    public S3Client s3Client() {
        return S3Client.builder()
                .region(Region.of(region))
                .credentialsProvider(DefaultCredentialsProvider.create())
                .build();
    }

    @Bean
    public EcrClient ecrClient() {
        String ecrRegion = region;
        if (ecrRepositoryUri != null && !ecrRepositoryUri.isBlank() && ecrRepositoryUri.contains(".dkr.ecr.")) {
            try {
                // e.g. 123456789012.dkr.ecr.us-east-1.amazonaws.com/repo
                String registry = ecrRepositoryUri.substring(0, ecrRepositoryUri.indexOf('/'));
                String[] parts = registry.split("\\.");
                if (parts.length > 3) {
                    ecrRegion = parts[3];
                }
            } catch (Exception e) {
                // fallback to default
            }
        }
        return EcrClient.builder()
                .region(Region.of(ecrRegion))
                .credentialsProvider(DefaultCredentialsProvider.create())
                .build();
    }
}
