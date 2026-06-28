package com.interview.mainservice.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.services.ec2.Ec2Client;

@Configuration
public class AwsEc2Config {

    @Bean
    public Ec2Client ec2Client() {
        return Ec2Client.builder()
                .credentialsProvider(DefaultCredentialsProvider.create())
                .build();
    }
}
