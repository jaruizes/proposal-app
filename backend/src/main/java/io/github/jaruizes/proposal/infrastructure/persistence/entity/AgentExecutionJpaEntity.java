package io.github.jaruizes.proposal.infrastructure.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "agent_executions")
public class AgentExecutionJpaEntity {
    @Id
    private UUID id;
    @Column(name = "offer_id")
    private UUID offerId;
    private String phase;
    @Column(name = "agent_key")
    private String agentKey;
    private String status;
    @Column(columnDefinition = "text")
    private String objective;
    @Column(columnDefinition = "text")
    private String output;
    private String model;
    @Column(name = "input_tokens")
    private long inputTokens;
    @Column(name = "output_tokens")
    private long outputTokens;
    @Column(name = "provider_request_id")
    private String providerRequestId;
    @Column(name = "started_at")
    private Instant startedAt;
    @Column(name = "completed_at")
    private Instant completedAt;
    @Column(name = "error_message", columnDefinition = "text")
    private String errorMessage;

    public AgentExecutionJpaEntity() {}

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public UUID getOfferId() { return offerId; }
    public void setOfferId(UUID offerId) { this.offerId = offerId; }
    public String getPhase() { return phase; }
    public void setPhase(String phase) { this.phase = phase; }
    public String getAgentKey() { return agentKey; }
    public void setAgentKey(String agentKey) { this.agentKey = agentKey; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getObjective() { return objective; }
    public void setObjective(String objective) { this.objective = objective; }
    public String getOutput() { return output; }
    public void setOutput(String output) { this.output = output; }
    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public long getInputTokens() { return inputTokens; }
    public void setInputTokens(long inputTokens) { this.inputTokens = inputTokens; }
    public long getOutputTokens() { return outputTokens; }
    public void setOutputTokens(long outputTokens) { this.outputTokens = outputTokens; }
    public String getProviderRequestId() { return providerRequestId; }
    public void setProviderRequestId(String providerRequestId) { this.providerRequestId = providerRequestId; }
    public Instant getStartedAt() { return startedAt; }
    public void setStartedAt(Instant startedAt) { this.startedAt = startedAt; }
    public Instant getCompletedAt() { return completedAt; }
    public void setCompletedAt(Instant completedAt) { this.completedAt = completedAt; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
}
