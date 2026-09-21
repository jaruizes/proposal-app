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
      libreoffice-impress \
      fontconfig \
      fonts-dejavu-core \
      fonts-liberation && \
    rm -rf /var/lib/apt/lists/*


WORKDIR /app

COPY --from=backend-build /workspace/target/proposal-platform-backend-0.1.0-SNAPSHOT.jar /app/app.jar

RUN mkdir -p /app/workspace

EXPOSE 8080

ENTRYPOINT ["java","-jar","/app/app.jar"]
