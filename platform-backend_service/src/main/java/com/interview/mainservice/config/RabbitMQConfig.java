package com.interview.mainservice.config;

import org.springframework.amqp.core.Queue;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    @Bean
    public Queue gradingQueue(@Value("${app.grading-queue:grading-queue}") String queueName) {
        return new Queue(queueName, true);
    }
}
