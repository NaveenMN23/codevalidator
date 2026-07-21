package com.interview.mainservice.testreport;

import com.interview.mainservice.dto.TestCaseResult;
import com.interview.mainservice.dto.TestCaseResult.Status;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

/**
 * Parses JUnit XML ({@code <testsuite><testcase>...}) into {@link TestCaseResult}s. Maven
 * Surefire emits this natively; pytest (--junitxml) and Jest (jest-junit) can be configured to
 * emit the same schema later, so this parser is not Java-specific — only the report file glob
 * (sandbox-runner) and the expected/actual extractor ({@link ExtractorRegistry}) are.
 */
public final class JUnitXmlReportParser {

    private static final Logger log = LoggerFactory.getLogger(JUnitXmlReportParser.class);

    private JUnitXmlReportParser() {
    }

    public static List<TestCaseResult> parse(List<ReportFile> reportFiles, String language) {
        ExpectedActualExtractor extractor = ExtractorRegistry.forLanguage(language);
        List<TestCaseResult> results = new ArrayList<>();
        for (ReportFile reportFile : reportFiles) {
            try {
                results.addAll(parseOne(reportFile.content(), extractor));
            } catch (Exception e) {
                // One malformed/unexpected report file should never take down the whole
                // response — stdout/stderr remain available as the raw fallback either way.
                log.warn("Failed to parse test report {}: {}", reportFile.path(), e.getMessage());
            }
        }
        return results;
    }

    private static List<TestCaseResult> parseOne(String xml, ExpectedActualExtractor extractor) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        // The XML text can contain candidate-influenced strings (test names, assertion
        // messages) even though the document itself is Surefire-generated — disable DTD/
        // external-entity resolution as a zero-cost hardening measure against XXE.
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        factory.setXIncludeAware(false);
        factory.setExpandEntityReferences(false);

        DocumentBuilder builder = factory.newDocumentBuilder();
        Document doc = builder.parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)));

        List<TestCaseResult> results = new ArrayList<>();
        NodeList testCases = doc.getElementsByTagName("testcase");
        for (int i = 0; i < testCases.getLength(); i++) {
            Element testCase = (Element) testCases.item(i);
            results.add(toTestCaseResult(testCase, extractor));
        }
        return results;
    }

    private static TestCaseResult toTestCaseResult(Element testCase, ExpectedActualExtractor extractor) {
        String name = testCase.getAttribute("name");
        String className = testCase.getAttribute("classname");

        Element failure = firstChild(testCase, "failure");
        Element error = firstChild(testCase, "error");
        Element skipped = firstChild(testCase, "skipped");

        Status status;
        Element problem;
        if (failure != null) {
            status = Status.FAILED;
            problem = failure;
        } else if (error != null) {
            status = Status.ERRORED;
            problem = error;
        } else if (skipped != null) {
            status = Status.SKIPPED;
            problem = skipped;
        } else {
            status = Status.PASSED;
            problem = null;
        }

        if (problem == null) {
            return new TestCaseResult(name, className, status, null, null, null, null);
        }

        String message = problem.hasAttribute("message") ? problem.getAttribute("message") : null;
        String stackTrace = textContent(problem);
        Optional<ExpectedActualExtractor.ExpectedActual> expectedActual =
                extractor.extract(message != null ? message : stackTrace);

        return new TestCaseResult(
                name,
                className,
                status,
                message,
                expectedActual.map(ExpectedActualExtractor.ExpectedActual::expected).orElse(null),
                expectedActual.map(ExpectedActualExtractor.ExpectedActual::actual).orElse(null),
                stackTrace);
    }

    private static Element firstChild(Element parent, String tagName) {
        NodeList children = parent.getElementsByTagName(tagName);
        return children.getLength() > 0 ? (Element) children.item(0) : null;
    }

    private static String textContent(Element element) {
        Node textNode = element.getFirstChild();
        String text = textNode != null ? textNode.getNodeValue() : null;
        return text != null && !text.isBlank() ? text.trim() : null;
    }
}
