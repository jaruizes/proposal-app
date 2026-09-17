FROM node:22-bookworm-slim AS mcp-build
WORKDIR /build/mcp/google-workspace
COPY mcp/google-workspace/package.json ./
RUN npm install
COPY mcp/google-workspace/tsconfig.json ./
COPY mcp/google-workspace/src ./src
RUN npm run build

FROM node:22-bookworm-slim AS node-runtime

FROM maven:3.9.11-eclipse-temurin-21 AS backend-build
WORKDIR /workspace
COPY backend/pom.xml ./pom.xml
COPY backend/src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre-jammy

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      libreoffice-core \
      libreoffice-writer \
      libreoffice-calc \
      libreoffice-impress && \
    rm -rf /var/lib/apt/lists/*

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/bin/npm /usr/local/bin/npm
COPY --from=node-runtime /usr/local/bin/npx /usr/local/bin/npx
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules

WORKDIR /app

COPY --from=backend-build /workspace/target/proposal-platform-backend-0.1.0-SNAPSHOT.jar /app/app.jar
COPY --from=mcp-build /build/mcp/google-workspace /app/mcp/google-workspace

RUN mkdir -p /app/workspace /app/.secrets

EXPOSE 8080

ENTRYPOINT ["java","-jar","/app/app.jar"]
