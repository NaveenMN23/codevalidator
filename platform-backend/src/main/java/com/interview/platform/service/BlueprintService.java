package com.interview.platform.service;

import com.interview.platform.model.Blueprint;
import com.interview.platform.repository.BlueprintRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
@Slf4j
public class BlueprintService {

    private final BlueprintRepository blueprintRepository;
    private final RedisTemplate<String, Object> redisTemplate;

    private static final String BLUEPRINT_CACHE_PREFIX = "blueprint:";

    @Transactional
    public void saveBlueprint(String challengeId, Map<String, Object> blueprintJson) {
        log.info("Saving blueprint for challenge: {}", challengeId);
        
        Blueprint blueprint = Blueprint.builder()
                .challengeId(challengeId)
                .blueprintJson(blueprintJson)
                .build();
        
        blueprintRepository.save(blueprint);
        
        // Cache in Redis
        String cacheKey = BLUEPRINT_CACHE_PREFIX + challengeId;
        redisTemplate.opsForValue().set(cacheKey, blueprintJson, Duration.ofDays(7));
    }

    @SuppressWarnings("unchecked")
    public Optional<Map<String, Object>> getBlueprint(String challengeId) {
        String cacheKey = BLUEPRINT_CACHE_PREFIX + challengeId;
        
        // Try cache first
        Object cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached instanceof Map) {
            return Optional.of((Map<String, Object>) cached);
        }
        
        // Fallback to DB
        return blueprintRepository.findById(challengeId)
                .map(Blueprint::getBlueprintJson)
                .map(json -> {
                    redisTemplate.opsForValue().set(cacheKey, json, Duration.ofDays(7));
                    return json;
                });
    }
}
