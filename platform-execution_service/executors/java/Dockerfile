FROM maven:3.9-eclipse-temurin-21

WORKDIR /build
COPY pom.xml .
COPY src/ src/
# Full test run bakes both declared dependencies AND build-lifecycle plugins (compiler,
# resources, surefire, jar) into the local Maven repo so offline mode works at runtime.
RUN mvn -B test

WORKDIR /app

RUN apt-get update && apt-get install -y python3 python3-pip --no-install-recommends \
    && pip3 install --no-cache-dir fastapi uvicorn --break-system-packages \
    && rm -rf /var/lib/apt/lists/*

COPY ../sandbox_server.py .

CMD ["python3", "-m", "uvicorn", "sandbox_server:app", "--host", "0.0.0.0", "--port", "8080"]
