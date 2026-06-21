package com.interview.admin.security;

import com.interview.admin.repository.UserRepository;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.lang.NonNull;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class AdminJwtAuthFilter extends OncePerRequestFilter {

    private final JwtService jwtService;
    private final UserRepository userRepository;

    public AdminJwtAuthFilter(JwtService jwtService, UserRepository userRepository) {
        this.jwtService = jwtService;
        this.userRepository = userRepository;
    }

    @Override
    protected void doFilterInternal(@NonNull HttpServletRequest request,
                                     @NonNull HttpServletResponse response,
                                     @NonNull FilterChain filterChain) throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            String token = header.substring(7);
            Optional<UUID> userId = jwtService.validateAndGetUserId(token);
            if (userId.isPresent() && SecurityContextHolder.getContext().getAuthentication() == null) {
                userRepository.findById(userId.get()).ifPresent(user -> {
                    if (user.isAdmin()) {
                        var auth = new UsernamePasswordAuthenticationToken(userId.get(), null, List.of());
                        SecurityContextHolder.getContext().setAuthentication(auth);
                    }
                });
            }
        }
        filterChain.doFilter(request, response);
    }
}
