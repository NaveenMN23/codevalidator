FROM node:20-slim
RUN apt-get update && apt-get install -y python3 make g++ --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY package.json .
# Install to /node_modules (root) so Node.js resolution finds packages from any working dir.
RUN npm install --prefer-offline --no-audit && \
    mv /build/node_modules /node_modules

# Create the app working dir with a shared node_modules.
WORKDIR /app
RUN ln -s /node_modules /app/node_modules
