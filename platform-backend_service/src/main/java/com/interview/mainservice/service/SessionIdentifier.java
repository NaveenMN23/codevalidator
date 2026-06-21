package com.interview.mainservice.service;

import java.util.UUID;

/**
 * Shared by RunService and SubmitService so Submit reuses the exact same session/container
 * Run created — used verbatim as a staging-dir name and inside Docker volume bind-mount specs
 * ("source:dest:mode") on the Execution Service side, so it must not contain ':' or '/'.
 */
final class SessionIdentifier {

    private SessionIdentifier() {
    }

    static String of(UUID userId, UUID problemId) {
        return userId + "_" + problemId;
    }
}
