FROM codercom/code-server:latest

USER root

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

WORKDIR /workspace

COPY package.json package-lock.json ./
COPY apps/gold-master-node/package.json ./apps/gold-master-node/

RUN npm install

COPY . .

EXPOSE 8080

USER coder

CMD ["code-server", "--bind-addr", "0.0.0.0:8080", "--auth", "none", "/workspace"]
