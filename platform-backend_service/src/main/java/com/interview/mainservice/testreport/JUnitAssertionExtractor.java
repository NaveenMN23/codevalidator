package com.interview.mainservice.testreport;

import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Matches JUnit5/opentest4j's {@code AssertionFailedError} message format, e.g.:
 * {@code expected: <200 OK> but was: <404 NOT_FOUND>}
 */
public class JUnitAssertionExtractor implements ExpectedActualExtractor {

    private static final Pattern EXPECTED_BUT_WAS =
            Pattern.compile("(?s)expected:\\s*<(.*?)>\\s*but was:\\s*<(.*?)>");

    @Override
    public Optional<ExpectedActual> extract(String message) {
        if (message == null) {
            return Optional.empty();
        }
        Matcher matcher = EXPECTED_BUT_WAS.matcher(message);
        if (matcher.find()) {
            return Optional.of(new ExpectedActual(matcher.group(1).trim(), matcher.group(2).trim()));
        }
        return Optional.empty();
    }
}
