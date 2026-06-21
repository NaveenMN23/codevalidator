package com.platform.base;

// Exists only so `mvn test` during the image build exercises the full default lifecycle
// (compiler, resources, surefire, jar plugins) — `dependency:go-offline` alone only resolves
// declared <dependencies>, not the build-lifecycle plugins needed to actually run tests.
public class Placeholder {
}
