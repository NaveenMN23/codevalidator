package com.interview.mainservice.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
public class RedisSessionStore {

    private static final String KEY_PREFIX = "fargate:session:";

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

    private String key(String sessionId) {
        return KEY_PREFIX + sessionId;
    }

    public record SessionEntry(String privateIp, String taskArn) {}
}
