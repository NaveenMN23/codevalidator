package com.interview.platform.service;

import com.interview.platform.dto.AuthResponse;
import com.interview.platform.dto.LoginRequest;
import com.interview.platform.dto.SignupRequest;
import com.interview.platform.model.User;
import com.interview.platform.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public AuthResponse signup(SignupRequest request) {
        if (userRepository.findByEmail(request.getEmail()).isPresent()) {
            throw new RuntimeException("Email already registered");
        }
        if (userRepository.findByUsername(request.getUsername()).isPresent()) {
            throw new RuntimeException("Username already taken");
        }

        User user = User.builder()
                .email(request.getEmail())
                .username(request.getUsername())
                .password(passwordEncoder.encode(request.getPassword()))
                .name(request.getName())
                .build();

        User savedUser = userRepository.save(user);
        return mapToResponse(savedUser);
    }

    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new RuntimeException("User not found"));

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new RuntimeException("Invalid password");
        }

        return mapToResponse(user);
    }

    private AuthResponse mapToResponse(User user) {
        AuthResponse response = new AuthResponse();
        response.setId(user.getId());
        response.setEmail(user.getEmail());
        response.setUsername(user.getUsername());
        response.setName(user.getName());
        return response;
    }
}
