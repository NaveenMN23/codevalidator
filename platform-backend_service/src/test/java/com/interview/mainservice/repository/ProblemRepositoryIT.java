package com.interview.mainservice.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.interview.mainservice.model.Difficulty;
import com.interview.mainservice.model.Problem;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@Testcontainers
class ProblemRepositoryIT {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @DynamicPropertySource
    static void registerProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private ProblemRepository problemRepository;

    @Test
    void persistsAndReadsBackAProblemWithTags() {
        Problem problem = Problem.create("two-sum", "Two Sum", "Find two numbers that sum to a target.",
                Difficulty.EASY, "challenges/two-sum/boilerplate.zip", List.of("arrays", "hash-map"), "easy");

        problemRepository.save(problem);

        Problem found = problemRepository.findBySlug("two-sum").orElseThrow();
        assertThat(found.getTitle()).isEqualTo("Two Sum");
        assertThat(found.getTags()).containsExactlyInAnyOrder("arrays", "hash-map");
    }
}
