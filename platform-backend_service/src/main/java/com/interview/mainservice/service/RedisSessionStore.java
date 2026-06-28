package com.interview.mainservice.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.concurrent.TimeUnit;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
public class RedisSessionStore {

    private static final String KEY_PREFIX = "fargate:session:";
    private static final String SPAWNING_KEY_PREFIX = "fargate:spawning:";

    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;

    public RedisSessionStore(StringRedisTemplate redis, ObjectMapper objectMapper) {
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
                .setIfAbsent(spawningKey(sessionId), "1", ttlSeconds, TimeUnit.SECONDS));
    }

    public void clearSpawning(String sessionId) {
        redis.delete(spawningKey(sessionId));
    }

    private String key(String sessionId) {
        return KEY_PREFIX + sessionId;
    }

    private String spawningKey(String sessionId) {
        return SPAWNING_KEY_PREFIX + sessionId;
    }

    public Set<String> getActiveTaskArns() {
        Set<String> keys = redis.keys(KEY_PREFIX + "*");
        if (keys == null || keys.isEmpty()) return Set.of();
        return keys.stream()
                .map(k -> redis.opsForValue().get(k))
                .filter(json -> json != null)
                .map(json -> {
                    try {
                        return objectMapper.readValue(json, SessionEntry.class).taskArn();
                    } catch (JsonProcessingException e) {
                        return null;
                    }
                })
                .filter(arn -> arn != null)
                .collect(Collectors.toSet());
    }

    public record SessionEntry(String privateIp, String taskArn) {}
}
