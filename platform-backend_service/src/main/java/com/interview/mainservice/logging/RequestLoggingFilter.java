package com.interview.mainservice.logging;

import jakarta.servlet.AsyncEvent;
import jakarta.servlet.AsyncListener;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.lang.NonNull;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Logs one access-log line per request: method, path, status, latency, and the
 * authenticated userId (if any). Run/Submit complete via DeferredResult on a virtual
 * thread (see ExecutionConfig), so the response isn't final when this filter's
 * doFilterInternal returns for those endpoints — an AsyncListener defers the log line
 * until the async dispatch actually completes instead of logging a premature status.
 */
@Component
public class RequestLoggingFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(RequestLoggingFilter.class);

    @Override
    protected boolean shouldNotFilter(@NonNull HttpServletRequest request) {
        return request.getRequestURI().startsWith("/actuator");
    }

    @Override
    protected void doFilterInternal(@NonNull HttpServletRequest request,
                                     @NonNull HttpServletResponse response,
                                     @NonNull FilterChain filterChain) throws ServletException, IOException {
        long startTime = System.currentTimeMillis();
        try {
            filterChain.doFilter(request, response);
        } finally {
            Object principal = currentPrincipal();
            if (request.isAsyncStarted()) {
                request.getAsyncContext().addListener(new AsyncListener() {
                    @Override
                    public void onComplete(AsyncEvent event) {
                        logRequest(request, response, startTime, principal);
                    }

                    @Override
                    public void onTimeout(AsyncEvent event) {
                    }

                    @Override
                    public void onError(AsyncEvent event) {
                    }

                    @Override
                    public void onStartAsync(AsyncEvent event) {
                    }
                });
            } else {
                logRequest(request, response, startTime, principal);
            }
        }
    }

    private Object currentPrincipal() {
        var authentication = SecurityContextHolder.getContext().getAuthentication();
        return authentication != null ? authentication.getPrincipal() : null;
    }

    private void logRequest(HttpServletRequest request, HttpServletResponse response, long startTime, Object principal) {
        long durationMs = System.currentTimeMillis() - startTime;
        MDC.put(TraceIdFilter.TRACE_ID_ATTRIBUTE, (String) request.getAttribute(TraceIdFilter.TRACE_ID_ATTRIBUTE));
        try {
            log.info("{} {} -> {} ({}ms) userId={}", request.getMethod(), request.getRequestURI(),
                    response.getStatus(), durationMs, principal != null ? principal : "anonymous");
        } finally {
            MDC.remove(TraceIdFilter.TRACE_ID_ATTRIBUTE);
        }
    }
}
