package com.interview.mainservice.service;

import com.interview.mainservice.dto.AuthResponse;
import com.interview.mainservice.dto.LoginRequest;
import com.interview.mainservice.dto.SignupRequest;
import com.interview.mainservice.security.JwtService;
import com.interview.mainservice.model.AuthProvider;
import com.interview.mainservice.model.User;
import com.interview.mainservice.repository.UserRepository;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtService jwtService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public AuthResponse signup(SignupRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email already registered");
        }
        User user = User.createLocal(request.email(), passwordEncoder.encode(request.password()), request.displayName());
        userRepository.save(user);
        return new AuthResponse(jwtService.issueToken(user.getId(), user.getEmail()), user.getId(), user.getEmail());
    }

    @Retryable(retryFor = DataAccessException.class, maxAttempts = 3, backoff = @Backoff(delay = 1000, multiplier = 2.0))
    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.email())
                .filter(u -> u.getAuthProvider() == AuthProvider.LOCAL)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials"));

        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials");
        }

        return new AuthResponse(jwtService.issueToken(user.getId(), user.getEmail()), user.getId(), user.getEmail());
    }
}
