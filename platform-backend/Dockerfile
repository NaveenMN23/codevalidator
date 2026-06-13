# Use a Maven image with JDK 21 to build and run the app
FROM maven:3.9.6-eclipse-temurin-21-alpine

WORKDIR /app

# Copy pom.xml and source code
COPY pom.xml .
COPY src ./src

# Build the application
RUN mvn clean package -DskipTests

# Run the application
ENTRYPOINT ["java", "-jar", "target/platform-backend-0.0.1-SNAPSHOT.jar"]
