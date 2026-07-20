package com.interview.mainservice.testreport;

import java.util.Optional;

/**
 * Selects the expected/actual extractor for a language. This is the extension point for
 * adding pytest/Jest support later: register a new extractor here without touching the
 * XML parser or the {@code TestCaseResult} shape.
 */
public final class ExtractorRegistry {

    private static final ExpectedActualExtractor JAVA_EXTRACTOR = new JUnitAssertionExtractor();
    private static final ExpectedActualExtractor NO_OP_EXTRACTOR = message -> Optional.empty();

    private ExtractorRegistry() {
    }

    public static ExpectedActualExtractor forLanguage(String language) {
        if ("java".equals(language)) {
            return JAVA_EXTRACTOR;
        }
        return NO_OP_EXTRACTOR;
    }
}
