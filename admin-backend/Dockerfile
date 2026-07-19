FROM golang:1.22-alpine AS go-build
WORKDIR /app
COPY src/main/resources/sandbox-runner/ ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o sandbox-runner-bin main.go

FROM maven:3.9.6-eclipse-temurin-21-alpine AS build
WORKDIR /app
COPY pom.xml .
RUN mvn -B dependency:go-offline
COPY src ./src
COPY --from=go-build /app/sandbox-runner-bin ./src/main/resources/sandbox-runner/sandbox-runner-bin
RUN mvn -B clean package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN apk add --no-cache docker-cli docker-cli-buildx
RUN addgroup -S app && adduser -S app -G app
COPY --from=build /app/target/admin-backend-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "app.jar"]
