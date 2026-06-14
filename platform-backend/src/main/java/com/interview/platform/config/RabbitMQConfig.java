package com.interview.platform.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String GRADING_QUEUE = "grading-queue";
    public static final String GRADING_RESULTS_QUEUE = "grading-results-queue";
    public static final String EXCHANGE = "interview-exchange";
    public static final String ROUTING_KEY = "grading.key";

    @Bean
    public Queue gradingQueue() {
        return new Queue(GRADING_QUEUE, true);
    }

    @Bean
    public Queue resultsQueue() {
        return new Queue(GRADING_RESULTS_QUEUE, true);
    }

    @Bean
    public TopicExchange exchange() {
        return new TopicExchange(EXCHANGE);
    }

    @Bean
    public Binding binding(@Qualifier("gradingQueue") Queue gradingQueue, TopicExchange exchange) {
        return BindingBuilder.bind(gradingQueue).to(exchange).with(ROUTING_KEY);
    }

    @Bean
    public org.springframework.amqp.support.converter.MessageConverter jsonMessageConverter() {
        return new org.springframework.amqp.support.converter.Jackson2JsonMessageConverter();
    }
}
