package com.interview.mainservice.service;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.dto.RunResponse;
import io.github.resilience4j.bulkhead.annotation.Bulkhead;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Plain blocking HTTP client for the Execution Service's /execute endpoint. Deliberately
 * not reactive (no WebClient) — this is meant to be called from a virtual thread (see
 * RunService), where a blocking call is cheap and parks without holding a platform thread.
 * See docs/design/deferred-eager-final-architecture.md §3.
 */
@Component
public class ExecutionServiceClient {

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final String baseUrl;

    public ExecutionServiceClient(@Value("${app.execution-service.base-url}") String baseUrl) {
        this.baseUrl = baseUrl;
    }

    // Semaphore bulkhead: bounds concurrent calls to the Execution Service's real capacity.
    // Deliberately restores the admission control that a bounded Tomcat thread pool used to
    // provide by accident, now that the caller runs on a virtual thread instead (see
    // docs/design/deferred-eager-final-architecture.md §3.3).
    @Bulkhead(name = "executionService", type = Bulkhead.Type.SEMAPHORE)
    public RunResponse execute(String sessionId, String challengeId, String language,
                                Map<String, String> files, String command) {
        try {
            ExecuteRequestBody body = new ExecuteRequestBody(sessionId, challengeId, language, files, command);
            String json = objectMapper.writeValueAsString(body);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/execute"))
                    .timeout(Duration.ofSeconds(90))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();

            // Plain blocking call — runs on a virtual thread, parks cheaply while waiting.
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() != 200) {
                return new RunResponse(false, "", extractDetail(response.body(), response.statusCode()), -1);
            }

            ExecuteResponseBody parsed = objectMapper.readValue(response.body(), ExecuteResponseBody.class);
            return new RunResponse(parsed.success(), parsed.stdout(), parsed.stderr(), parsed.exitCode());
        } catch (IOException e) {
            return new RunResponse(false, "", "Failed to reach Execution Service: " + e.getMessage(), -1);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return new RunResponse(false, "", "Execution interrupted", -1);
        }
    }

    // Same shared Bulkhead instance as execute() — Run and Submit compete for the same
    // Execution Service/Docker host capacity, so they share one concurrency budget rather than
    // each getting their own.
    @Bulkhead(name = "executionService", type = Bulkhead.Type.SEMAPHORE)
    public RunResponse submit(String sessionId, String challengeId, String tier, String language,
                               Map<String, String> files, String command) {
        try {
            SubmitRequestBody body = new SubmitRequestBody(sessionId, challengeId, tier, language, files, command);
            String json = objectMapper.writeValueAsString(body);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/submit"))
                    .timeout(Duration.ofSeconds(90))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() != 200) {
                return new RunResponse(false, "", extractDetail(response.body(), response.statusCode()), -1);
            }

            ExecuteResponseBody parsed = objectMapper.readValue(response.body(), ExecuteResponseBody.class);
            return new RunResponse(parsed.success(), parsed.stdout(), parsed.stderr(), parsed.exitCode());
        } catch (IOException e) {
            return new RunResponse(false, "", "Failed to reach Execution Service: " + e.getMessage(), -1);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return new RunResponse(false, "", "Execution interrupted", -1);
        }
    }

    private String extractDetail(String body, int statusCode) {
        try {
            JsonNode node = objectMapper.readTree(body);
            if (node.has("detail")) return node.get("detail").asText();
        } catch (Exception ignored) {}
        return "Execution Service error (HTTP " + statusCode + ")";
    }

    private record ExecuteRequestBody(String sessionId, String challengeId, String language,
                                       Map<String, String> files, String command) {
    }

    private record SubmitRequestBody(String sessionId, String challengeId, String tier, String language,
                                      Map<String, String> files, String command) {
    }

    private record ExecuteResponseBody(boolean success, String stdout, String stderr,
                                        @JsonProperty("exit_code") int exitCode) {
    }
}
