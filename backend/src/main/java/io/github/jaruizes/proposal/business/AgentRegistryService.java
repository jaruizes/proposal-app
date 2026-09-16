package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import io.github.jaruizes.proposal.domain.model.AgentDefinition;
import org.springframework.stereotype.Service;
import java.util.*;

@Service
public class AgentRegistryService {
    private final Map<String, AgentDefinition> agents = new LinkedHashMap<>();
    public AgentRegistryService() {
        register(new AgentDefinition("business-analyst","Business Analyst","Offer Owner",Set.of("opportunity-analysis","response-strategy","slide-planning","coherence-review"),Set.of("source.read","source.search","knowledge.search"),"prompts/business-analyst.md"));
        register(new AgentDefinition("solution-architect","Solution Architect","Solution Architect",Set.of("architecture-design","technical-decisions","source-analysis"),Set.of("source.read","source.search","knowledge.search","ontology.query"),"prompts/solution-architect.md"));
        register(new AgentDefinition("delivery-manager","Delivery Manager","Delivery Manager",Set.of("delivery-planning","work-breakdown","risk-coordination"),Set.of("source.read","source.search","knowledge.search"),"prompts/delivery-manager.md"));
        register(new AgentDefinition("presentation-builder","Presentation Builder","Presentation Builder",Set.of("presentation-materialization","visual-mapping"),Set.of("presentation.read","presentation.write","source.read"),"prompts/presentation-builder.md"));
        register(new AgentDefinition("security-specialist","Security Specialist","Specialist",Set.of("security-review","cryptography"),Set.of("source.read","knowledge.search"),"prompts/security-specialist.md"));
    }
    public void register(AgentDefinition definition){agents.put(definition.key(),definition);} public AgentDefinition get(String key){var a=agents.get(key);if(a==null)throw new DomainException("Unknown agent: "+key);return a;} public List<AgentDefinition> all(){return List.copyOf(agents.values());} public Optional<AgentDefinition> findByCapability(String c){return agents.values().stream().filter(a->a.capabilities().contains(c)).findFirst();}
}
