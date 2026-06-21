package com.interview.admin.service;

import com.interview.admin.dto.AuthResponse;
import com.interview.admin.dto.LoginRequest;
import com.interview.admin.model.User;
import com.interview.admin.repository.UserRepository;
import com.interview.admin.security.JwtService;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AdminAuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    public AdminAuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtService jwtService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials"));

        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials");
        }

        if (!user.isAdmin()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Admin access required");
        }

        return new AuthResponse(jwtService.issueToken(user.getId(), user.getEmail()), user.getId(), user.getEmail());
    }
}
