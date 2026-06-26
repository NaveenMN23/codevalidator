package com.interview.mainservice.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.lang.NonNull;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    // Fixed dev user UUID injected when auth is disabled
    private static final UUID DEV_USER_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");

    private final JwtService jwtService;
    private final boolean authRequired;

    public JwtAuthenticationFilter(JwtService jwtService,
                                    @Value("${app.security.auth-required:true}") boolean authRequired) {
        this.jwtService = jwtService;
        this.authRequired = authRequired;
    }

    @Override
    protected boolean shouldNotFilterAsyncDispatch() {
        // RunController completes its response via DeferredResult from a separate
        // (virtual-thread) executor, so the servlet container performs a second, async
        // dispatch back through the filter chain on a different thread to write the
        // response. OncePerRequestFilter skips itself on that dispatch by default, which
        // left SecurityContextHolder empty on that thread — Spring Security's
        // AuthorizationFilter then re-checks .authenticated() against that empty context
        // and rejects with 403, even though the original request was correctly
        // authenticated. Re-running this filter (cheap: just re-reads the Authorization
        // header, still present on the same HttpServletRequest) fixes it.
        return false;
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
                var authentication = new UsernamePasswordAuthenticationToken(userId.get(), null, List.of());
                SecurityContextHolder.getContext().setAuthentication(authentication);
            }
        } else if (!authRequired && SecurityContextHolder.getContext().getAuthentication() == null) {
            // Dev mode: no token present — set a fixed dev user so controllers that
            // use @AuthenticationPrincipal don't see a null userId.
            var authentication = new UsernamePasswordAuthenticationToken(DEV_USER_ID, null, List.of());
            SecurityContextHolder.getContext().setAuthentication(authentication);
        }
        filterChain.doFilter(request, response);
    }
}
