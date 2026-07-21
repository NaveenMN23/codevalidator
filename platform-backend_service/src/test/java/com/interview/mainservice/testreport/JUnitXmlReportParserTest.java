package com.interview.mainservice.testreport;

import static org.assertj.core.api.Assertions.assertThat;

import com.interview.mainservice.dto.TestCaseResult;
import com.interview.mainservice.dto.TestCaseResult.Status;
import java.util.List;
import org.junit.jupiter.api.Test;

class JUnitXmlReportParserTest {

    // Mirrors a real Surefire report for TrafficSignalServiceHiddenTest: one passing case,
    // one assertion failure (<failure>), and one uncaught exception (<error>) — the exact
    // shape this session's UnsupportedOperationException debugging thread produced.
    private static final String SAMPLE_XML = """
            <?xml version="1.0" encoding="UTF-8"?>
            <testsuite name="com.challenge.TrafficSignalServiceHiddenTest" tests="3" failures="1" errors="1">
              <testcase name="testConfigureSignalDuration_Idempotency" classname="com.challenge.TrafficSignalServiceHiddenTest" time="0.045"/>
              <testcase name="testConfigureSignalDuration_NotFound" classname="com.challenge.TrafficSignalServiceHiddenTest" time="0.031">
                <failure message="expected: &lt;404 NOT_FOUND&gt; but was: &lt;200 OK&gt;" type="org.opentest4j.AssertionFailedError">
            org.opentest4j.AssertionFailedError: expected: &lt;404 NOT_FOUND&gt; but was: &lt;200 OK&gt;
            \tat com.challenge.TrafficSignalServiceHiddenTest.testConfigureSignalDuration_NotFound(TrafficSignalServiceHiddenTest.java:60)
                </failure>
              </testcase>
              <testcase name="testConfigureSignalDuration_Success" classname="com.challenge.TrafficSignalServiceHiddenTest" time="0.028">
                <error message="Unimplemented method" type="java.lang.UnsupportedOperationException">
            java.lang.UnsupportedOperationException: Unimplemented method
            \tat com.challenge.services.TrafficSignalService.configureSignalDuration(TrafficSignalService.java:42)
                </error>
              </testcase>
            </testsuite>
            """;

    @Test
    void parsesPassedFailedAndErroredTestCases() {
        List<TestCaseResult> results = JUnitXmlReportParser.parse(
                List.of(new ReportFile("target/surefire-reports/TEST-Hidden.xml", SAMPLE_XML)), "java");

        assertThat(results).hasSize(3);

        TestCaseResult passed = findByName(results, "testConfigureSignalDuration_Idempotency");
        assertThat(passed.status()).isEqualTo(Status.PASSED);
        assertThat(passed.message()).isNull();
        assertThat(passed.expected()).isNull();
        assertThat(passed.actual()).isNull();

        TestCaseResult failed = findByName(results, "testConfigureSignalDuration_NotFound");
        assertThat(failed.status()).isEqualTo(Status.FAILED);
        assertThat(failed.expected()).isEqualTo("404 NOT_FOUND");
        assertThat(failed.actual()).isEqualTo("200 OK");
        assertThat(failed.stackTrace()).contains("AssertionFailedError");

        TestCaseResult errored = findByName(results, "testConfigureSignalDuration_Success");
        assertThat(errored.status()).isEqualTo(Status.ERRORED);
        assertThat(errored.message()).isEqualTo("Unimplemented method");
        assertThat(errored.stackTrace()).contains("UnsupportedOperationException");
    }

    @Test
    void unsupportedLanguageFallsBackToRawMessageWithoutExpectedActual() {
        List<TestCaseResult> results = JUnitXmlReportParser.parse(
                List.of(new ReportFile("report.xml", SAMPLE_XML)), "python");

        TestCaseResult failed = findByName(results, "testConfigureSignalDuration_NotFound");
        assertThat(failed.expected()).isNull();
        assertThat(failed.actual()).isNull();
        assertThat(failed.message()).contains("but was");
    }

    @Test
    void malformedXmlIsSkippedRatherThanThrowing() {
        List<TestCaseResult> results = JUnitXmlReportParser.parse(
                List.of(new ReportFile("bad.xml", "<not-valid-xml")), "java");

        assertThat(results).isEmpty();
    }

    private static TestCaseResult findByName(List<TestCaseResult> results, String name) {
        return results.stream()
                .filter(r -> r.name().equals(name))
                .findFirst()
                .orElseThrow(() -> new AssertionError("No test case named " + name));
    }
}
