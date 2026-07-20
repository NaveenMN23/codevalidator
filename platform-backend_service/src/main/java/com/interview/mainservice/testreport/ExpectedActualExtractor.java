package com.interview.mainservice.testreport;

import java.util.Optional;

/**
 * Pulls expected/actual values out of a failure message. Message formats differ per test
 * framework even though they all fit in JUnit XML's {@code message} attribute, so this is
 * looked up per-language via {@link ExtractorRegistry} rather than baked into the XML parser.
 */
public interface ExpectedActualExtractor {

    Optional<ExpectedActual> extract(String message);

    record ExpectedActual(String expected, String actual) {
    }
}
