package com.interview.mainservice.config;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Scoped virtual-thread executor used only by the Run/Submit call path (see
 * docs/design/deferred-eager-final-architecture.md §3.1). Deliberately not the global
 * spring.threads.virtual.enabled flag — every other endpoint keeps running on Tomcat's
 * ordinary platform-thread pool, unaffected.
 */
@Configuration
public class ExecutionConfig {

    @Bean
    public ExecutorService executionServiceExecutor() {
        return Executors.newVirtualThreadPerTaskExecutor();
    }
}
