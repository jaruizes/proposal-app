package io.github.jaruizes.proposal.business;

import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Registry for Proposal Copilot's validated SKILL contracts.
 *
 * The Markdown files under src/main/resources/skills are intentionally kept as
 * first-class, versioned execution contracts. The LLM receives the complete
 * selected SKILL on every AgentExecution. Deterministic workflow invariants are
 * additionally enforced in Java and are never delegated only to the model.
 */
@Service
public class SkillRegistryService {
    private final PromptService resources;
    private final Map<String, String> skills;

    public SkillRegistryService(PromptService resources) {
        this.resources = resources;
        var registered = new LinkedHashMap<String, String>();
        registered.put("create-offer", "skills/create-offer/SKILL.md");
        registered.put("ingest-sources", "skills/ingest-sources/SKILL.md");
        registered.put("analyze-opportunity", "skills/analyze-opportunity/SKILL.md");
        registered.put("build-strategy", "skills/build-strategy/SKILL.md");
        registered.put("define-solution", "skills/define-solution/SKILL.md");
        registered.put("design-proposal", "skills/design-proposal/SKILL.md");
        registered.put("generate-presentation", "skills/generate-presentation/SKILL.md");
        this.skills = Map.copyOf(registered);
    }

    public String load(String key) {
        var path = skills.get(key);
        if (path == null) {
            throw new IllegalArgumentException("Unknown skill: " + key);
        }
        return resources.load(path);
    }

    public Set<String> keys() {
        return skills.keySet();
    }

    public void verifyAllReadable() {
        skills.forEach((key, path) -> {
            var content = resources.load(path);
            if (content.isBlank()) {
                throw new IllegalStateException("Empty SKILL contract: " + key);
            }
        });
    }
}
