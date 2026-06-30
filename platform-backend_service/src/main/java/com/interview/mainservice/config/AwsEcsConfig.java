package com.interview.mainservice.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.services.ecs.EcsClient;

@Configuration
public class AwsEcsConfig {

    @Bean
    public EcsClient ecsClient() {
        return EcsClient.builder()
                .credentialsProvider(DefaultCredentialsProvider.create())
                .build();
    }
}
