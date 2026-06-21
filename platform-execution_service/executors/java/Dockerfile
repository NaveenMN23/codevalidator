FROM maven:3.9-eclipse-temurin-21
WORKDIR /build
COPY pom.xml .
COPY src/ src/
# Running the full `test` lifecycle (not just dependency:go-offline) bakes both the declared
# <dependencies> AND the build-lifecycle plugins (compiler, resources, surefire, jar) into the
# image's local Maven repo — go-offline alone only resolves dependencies, not the plugins
# needed to actually run `mvn test`, which left challenge submissions failing to resolve
# maven-resources-plugin etc. in offline mode.
RUN mvn -B test
WORKDIR /app
