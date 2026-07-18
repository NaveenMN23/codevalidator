# Use maven base image to support Java compilation
FROM maven:3.9-eclipse-temurin-21

# Install Node.js, Python 3.11, and pip
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

# Create a virtual environment for Python to avoid PEP 668 external-managed-environment errors
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Pre-warm Maven .m2 cache with Spring Boot 3.2.0 dependency tree so compile
# validation never needs network access at runtime inside the container.
COPY warmup-pom.xml /tmp/mvn-warmup/pom.xml
RUN mkdir -p /tmp/mvn-warmup/src/main/java/com/challenge \
    && printf 'package com.challenge;\npublic class App {}\n' \
       > /tmp/mvn-warmup/src/main/java/com/challenge/App.java \
    && mvn -B -f /tmp/mvn-warmup/pom.xml dependency:go-offline -q \
    && mvn -B -f /tmp/mvn-warmup/pom.xml test-compile -q \
    && rm -rf /tmp/mvn-warmup

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --timeout 300 --retries 5 -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Run main.py when the container launches
CMD ["python", "main.py"]
