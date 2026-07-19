"""Tests for _is_only_stub_related_test_failure — used at Phase 2a's skeleton
validation (now run_tests=True, actually executing the skeleton's own required starter
test, not just compiling it) to distinguish a genuine self-consistency bug from the
starter test harmlessly hitting a scenario's own not-yet-implemented stub method.
"""
from services.scaffold_generator import _is_only_stub_related_test_failure

# Real failure text captured from the live bug this check is built to NOT tolerate:
# ConnectionService.sendConnectionRequest correctly throws on a duplicate, but the
# skeleton's own starter test asserts no-throw against IDs its own Flyway seed data
# already made a duplicate — a genuine self-consistency bug, not a stub.
REAL_GENUINE_BUG_OUTPUT = """[ERROR] COMPILATION ERROR :
STDOUT:
[ERROR] Tests run: 3, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 1.975 s <<< FAILURE! -- in com.challenge.connection.ConnectionServiceTest
[ERROR] com.challenge.connection.ConnectionServiceTest.testSendConnectionRequest -- Time elapsed: 0.007 s <<< FAILURE!
org.opentest4j.AssertionFailedError: Unexpected exception thrown: java.lang.IllegalStateException: Connection request already exists
\tat org.junit.jupiter.api.AssertionFailureBuilder.build(AssertionFailureBuilder.java:152)
Caused by: java.lang.IllegalStateException: Connection request already exists
\tat com.challenge.connection.ConnectionService.sendConnectionRequest(ConnectionService.java:21)

[ERROR] Failures:
[ERROR]   ConnectionServiceTest.testSendConnectionRequest:20 Unexpected exception thrown: java.lang.IllegalStateException: Connection request already exists
[ERROR] Tests run: 3, Failures: 1, Errors: 0, Skipped: 0
"""

STUB_ONLY_OUTPUT = """[ERROR] Tests run: 5, Failures: 0, Errors: 1, Skipped: 0, Time elapsed: 1.2 s <<< FAILURE! -- in com.challenge.job.JobServiceTest
[ERROR] com.challenge.job.JobServiceTest.testPostJob -- Time elapsed: 0.010 s <<< ERROR!
java.lang.UnsupportedOperationException: not implemented: medium-job-posting
\tat com.challenge.job.JobService.postJob(JobService.java:15)
\tat com.challenge.job.JobServiceTest.testPostJob(JobServiceTest.java:22)

[ERROR] Failures:
[ERROR]   JobServiceTest.testPostJob:22 » UnsupportedOperation not implemented: medium-job-posting
"""

MIXED_OUTPUT = """[ERROR] Tests run: 5, Failures: 1, Errors: 1, Skipped: 0, Time elapsed: 1.2 s <<< FAILURE! -- in com.challenge.job.JobServiceTest
[ERROR] com.challenge.job.JobServiceTest.testPostJob -- Time elapsed: 0.010 s <<< ERROR!
java.lang.UnsupportedOperationException: not implemented: medium-job-posting
\tat com.challenge.job.JobService.postJob(JobService.java:15)

[ERROR] com.challenge.job.JobServiceTest.testListJobs -- Time elapsed: 0.005 s <<< FAILURE!
org.opentest4j.AssertionFailedError: expected: <2> but was: <0>
\tat com.challenge.job.JobServiceTest.testListJobs(JobServiceTest.java:30)
"""

PLAIN_COMPILE_ERROR_OUTPUT = """[ERROR] COMPILATION ERROR :
[ERROR] /tmp/x/src/main/java/com/challenge/job/JobService.java:[10,5] cannot find symbol
  symbol:   class List
  location: class com.challenge.job.JobService
"""


def test_genuine_bug_is_not_tolerated():
    assert _is_only_stub_related_test_failure(REAL_GENUINE_BUG_OUTPUT) is False


def test_stub_only_failure_is_tolerated():
    assert _is_only_stub_related_test_failure(STUB_ONLY_OUTPUT) is True


def test_mixed_stub_and_genuine_failure_is_not_tolerated():
    assert _is_only_stub_related_test_failure(MIXED_OUTPUT) is False


def test_plain_compile_error_is_not_tolerated():
    assert _is_only_stub_related_test_failure(PLAIN_COMPILE_ERROR_OUTPUT) is False


def test_empty_string_is_not_tolerated():
    assert _is_only_stub_related_test_failure("") is False
