package com.interview.admin.service;

class DockerfileTemplates {

    private DockerfileTemplates() {}

    static String build(String language, boolean hasDependencies) {
        if (!hasDependencies) {
            return "FROM platform/" + language + "-executor:latest\nWORKDIR /app\n";
        }
        return switch (language) {
            case "python" -> """
                    FROM platform/python-executor:latest
                    WORKDIR /build
                    COPY requirements.txt .
                    RUN pip install -r requirements.txt
                    WORKDIR /app
                    """;
            case "node" -> """
                    FROM platform/node-executor:latest
                    WORKDIR /build
                    COPY package.json .
                    RUN npm install
                    WORKDIR /app
                    """;
            default -> """
                    FROM platform/java-executor:latest
                    WORKDIR /build
                    COPY pom.xml .
                    RUN mvn -B dependency:go-offline
                    WORKDIR /app
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
