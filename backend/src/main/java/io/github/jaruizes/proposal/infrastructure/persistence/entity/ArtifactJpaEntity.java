package io.github.jaruizes.proposal.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "artifacts")
public class ArtifactJpaEntity {
    @Id
    private UUID id;
    @Column(name = "offer_id")
    private UUID offerId;
    private String phase;
    private String type;
    private int version;
    @Column(columnDefinition = "text")
    private String content;
    @Column(name = "created_at")
    private Instant createdAt;

    public ArtifactJpaEntity() {}

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public UUID getOfferId() { return offerId; }
    public void setOfferId(UUID offerId) { this.offerId = offerId; }
    public String getPhase() { return phase; }
    public void setPhase(String phase) { this.phase = phase; }
    public String getType() { return type; }
    public void setType(String type) { this.type = type; }
    public int getVersion() { return version; }
    public void setVersion(int version) { this.version = version; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
