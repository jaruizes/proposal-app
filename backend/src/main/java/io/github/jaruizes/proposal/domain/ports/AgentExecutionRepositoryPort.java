package io.github.jaruizes.proposal.domain.ports;
import io.github.jaruizes.proposal.domain.model.AgentExecution; import java.util.*;
public interface AgentExecutionRepositoryPort { AgentExecution save(AgentExecution execution); List<AgentExecution> findByOfferId(UUID offerId); }
