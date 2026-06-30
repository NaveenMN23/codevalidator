package com.interview.mainservice.repository;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
public class SessionRepository {

    private static final String KEY_PREFIX = "fargate:session:";
    private static final String SPAWNING_KEY_PREFIX = "fargate:spawning:";

    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;

    public SessionRepository(StringRedisTemplate redis, ObjectMapper objectMapper) {
        this.redis = redis;
        this.objectMapper = objectMapper;
    }

    public void setSession(String sessionId, String privateIp, String taskArn, long ttlSeconds) {
        SessionEntry entry = new SessionEntry(privateIp, taskArn);
        try {
            String json = objectMapper.writeValueAsString(entry);
            redis.opsForValue().set(key(sessionId), json, ttlSeconds, TimeUnit.SECONDS);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Failed to serialize session entry", e);
        }
    }

    public Optional<SessionEntry> getSession(String sessionId) {
        String json = redis.opsForValue().get(key(sessionId));
        if (json == null) return Optional.empty();
        try {
            return Optional.of(objectMapper.readValue(json, SessionEntry.class));
        } catch (JsonProcessingException e) {
            return Optional.empty();
        }
    }

    public void refreshTtl(String sessionId, long ttlSeconds) {
        redis.expire(key(sessionId), ttlSeconds, TimeUnit.SECONDS);
    }

    public void deleteSession(String sessionId) {
        redis.delete(key(sessionId));
    }

    public boolean tryMarkSpawning(String sessionId, long ttlSeconds) {
        return Boolean.TRUE.equals(redis.opsForValue()
                .setIfAbsent(spawningKey(sessionId), "pending", ttlSeconds, TimeUnit.SECONDS));
    }

    public void updateSpawningArn(String sessionId, String taskArn, long ttlSeconds) {
        redis.opsForValue().set(spawningKey(sessionId), taskArn, ttlSeconds, TimeUnit.SECONDS);
    }

    public void clearSpawning(String sessionId) {
        redis.delete(spawningKey(sessionId));
    }

    public Set<String> getActiveTaskArns() {
        Set<String> arns = new HashSet<>();

        Set<String> sessionKeys = redis.keys(KEY_PREFIX + "*");
        if (sessionKeys != null && !sessionKeys.isEmpty()) {
            List<String> values = redis.opsForValue().multiGet(new ArrayList<>(sessionKeys));
            if (values != null) {
                for (String json : values) {
                    if (json == null) continue;
                    try {
                        String arn = objectMapper.readValue(json, SessionEntry.class).taskArn();
                        if (arn != null) arns.add(arn);
                    } catch (JsonProcessingException ignored) {}
                }
            }
        }

        // Include ARNs for tasks mid-spawn (runTask called but setSession not yet called).
        // The spawning key value is "pending" initially and updated to the task ARN once runTask returns.
        Set<String> spawningKeys = redis.keys(SPAWNING_KEY_PREFIX + "*");
        if (spawningKeys != null && !spawningKeys.isEmpty()) {
            List<String> values = redis.opsForValue().multiGet(new ArrayList<>(spawningKeys));
            if (values != null) {
                for (String value : values) {
                    if (value != null && value.startsWith("arn:")) arns.add(value);
                }
            }
        }

        return arns;
    }

    private String key(String sessionId) {
        return KEY_PREFIX + sessionId;
    }

    private String spawningKey(String sessionId) {
        return SPAWNING_KEY_PREFIX + sessionId;
    }

    public record SessionEntry(String privateIp, String taskArn) {}
}
