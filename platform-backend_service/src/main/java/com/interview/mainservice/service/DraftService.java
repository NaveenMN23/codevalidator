package com.interview.mainservice.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.mainservice.model.Draft;
import com.interview.mainservice.repository.DraftRepository;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class DraftService {

    private final DraftRepository draftRepository;
    private final ObjectMapper objectMapper;

    public DraftService(DraftRepository draftRepository, ObjectMapper objectMapper) {
        this.draftRepository = draftRepository;
        this.objectMapper = objectMapper;
    }

    public Optional<Map<String, String>> getDraft(UUID userId, UUID problemId) {
        return draftRepository.findByUserIdAndProblemId(userId, problemId)
                .map(draft -> {
                    if (draft.getFilesJson() == null) return null;
                    try {
                        return objectMapper.readValue(draft.getFilesJson(), new TypeReference<Map<String, String>>() {});
                    } catch (JsonProcessingException e) {
                        return null;
                    }
                });
    }

    @Transactional
    public void saveDraft(UUID userId, UUID problemId, Map<String, String> files) {
        String json;
        try {
            json = objectMapper.writeValueAsString(files);
        } catch (JsonProcessingException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid files payload");
        }
        Draft draft = draftRepository.findByUserIdAndProblemId(userId, problemId)
                .orElseGet(() -> new Draft(userId, problemId, ""));
        draft.setFilesJson(json);
        draftRepository.save(draft);
    }

    @Transactional
    public void deleteDraft(UUID userId, UUID problemId) {
        draftRepository.deleteByUserIdAndProblemId(userId, problemId);
    }
}
