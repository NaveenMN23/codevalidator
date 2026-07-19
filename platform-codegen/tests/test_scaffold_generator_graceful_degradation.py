"""Tests for _is_test_execution_failure — used at Phase 2a's retry-exhaustion point to
decide whether it's safe to fall back to compile-only acceptance (a persisting TEST
failure, not a compile error) instead of hard-failing the whole generation. Real text
captured from the live run where this fallback was designed to matter: the LLM's patch
attempt at a genuine Mockito-mismatch bug introduced a NEW compile error, and by then
the skeleton-retry budget was exhausted.
"""
from services.scaffold_generator import _is_test_execution_failure

# Real captured output: the LLM's patch attempt broke compilation outright — must NOT
# fall back, this is a genuine, unresolved compile error.
REAL_COMPILE_ERROR_OUTPUT = """[ERROR] COMPILATION ERROR :
[ERROR] /tmp/tmpgilbd0sv/src/main/java/com/challenge/connection/ConnectionService.java:[19,95] missing return statement
[ERROR] Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin:3.11.0:compile (default-compile) on project challenge: Compilation failure
[ERROR] /tmp/tmpgilbd0sv/src/main/java/com/challenge/connection/ConnectionService.java:[19,95] missing return statement
[ERROR] -> [Help 1]
"""

# Real captured output: code compiled fine; two test failures (one genuine Mockito
# mismatch, one stub hit) — safe to fall back to compile-only acceptance if retries run out.
REAL_MIXED_TEST_FAILURE_OUTPUT = """[ERROR] Tests run: 4, Failures: 2, Errors: 0, Skipped: 0, Time elapsed: 0.532 s <<< FAILURE! -- in com.challenge.ConnectionServiceTest
[ERROR] com.challenge.ConnectionServiceTest.testAcceptConnectionRequest_updatesStatus -- Time elapsed: 0.010 s <<< FAILURE!
Wanted but not invoked:
connectionRepository.save(
    com.challenge.models.Connection@5116ac09
);
-> at com.challenge.ConnectionServiceTest.testAcceptConnectionRequest_updatesStatus(ConnectionServiceTest.java:61)

[ERROR] com.challenge.ConnectionServiceTest.testSendConnectionRequest_noDuplicate -- Time elapsed: 0.004 s <<< FAILURE!
org.opentest4j.AssertionFailedError: Unexpected exception thrown: java.lang.UnsupportedOperationException: not implemented: medium-connection-request
\tat com.challenge.connection.ConnectionService.sendConnectionRequest(ConnectionService.java:28)
"""

PLAIN_SUCCESS_OUTPUT = ""


def test_genuine_compile_error_does_not_fall_back():
    assert _is_test_execution_failure(REAL_COMPILE_ERROR_OUTPUT) is False


def test_mixed_test_execution_failure_is_safe_to_fall_back():
    assert _is_test_execution_failure(REAL_MIXED_TEST_FAILURE_OUTPUT) is True


def test_empty_output_does_not_fall_back():
    assert _is_test_execution_failure(PLAIN_SUCCESS_OUTPUT) is False
