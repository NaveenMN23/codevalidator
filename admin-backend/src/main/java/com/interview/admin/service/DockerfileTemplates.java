package com.interview.admin.service;

class DockerfileTemplates {

    private DockerfileTemplates() {}

    static String build(String language, boolean hasDependencies) {
        if (!hasDependencies) {
            return "FROM platform/" + language + "-executor:latest\nWORKDIR /app\n";
        }
        return switch (language) {
            case "python" -> """
                    FROM python:3.11-alpine
                    WORKDIR /app
                    COPY requirements.txt .
                    RUN pip install --no-cache-dir -r requirements.txt
                    COPY sandbox-runner-bin /usr/local/bin/sandbox-runner
                    EXPOSE 8080
                    CMD ["/usr/local/bin/sandbox-runner", "--port", "8080"]
                    """;
            case "node" -> """
                    FROM node:20-alpine
                    RUN apk add --no-cache python3 make g++
                    WORKDIR /app
                    COPY package.json .
                    RUN npm install --prefer-offline --no-audit
                    COPY sandbox-runner-bin /usr/local/bin/sandbox-runner
                    EXPOSE 8080
                    CMD ["/usr/local/bin/sandbox-runner", "--port", "8080"]
                    """;
            default -> """
                    FROM maven:3.9.6-eclipse-temurin-21-alpine
                    WORKDIR /app
                    COPY pom.xml .
                    RUN mvn -B dependency:go-offline && \\
                        mkdir -p src/main/java src/test/java && \\
                        echo 'public class Dummy {}' > src/main/java/Dummy.java && \\
                        echo 'public class DummyTest {}' > src/test/java/DummyTest.java && \\
                        mvn -B test || true && \\
                        rm -rf src target
                    COPY sandbox-runner-bin /usr/local/bin/sandbox-runner
                    EXPOSE 8080
                    CMD ["/usr/local/bin/sandbox-runner", "--port", "8080"]
                    """;
        };
    }

    static String depFileName(String language) {
        return switch (language) {
            case "python" -> "requirements.txt";
            case "node" -> "package.json";
            default -> "pom.xml";
        };
    }
}
