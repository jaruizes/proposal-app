package io.github.jaruizes.proposal.business;

import org.springframework.stereotype.Service;

import java.util.Map;

/**
 * Registry for the validated Proposal Copilot SKILL contracts.
 * Skills remain versioned resources; workflow rules that must be deterministic
 * are also enforced in Java rather than delegated only to the model.
 */
@Service
public class SkillRegistryService {
    private final PromptService resources;
    private final Map<String,String> skills = Map.of(
            "ingest-sources", "skills/ingest-sources/SKILL.md",
            "analyze-opportunity", "skills/analyze-opportunity/SKILL.md",
            "build-strategy", "skills/build-strategy/SKILL.md",
            "define-solution", "skills/define-solution/SKILL.md",
            "design-proposal", "skills/design-proposal/SKILL.md",
            "generate-presentation", "skills/generate-presentation/SKILL.md"
    );

    public SkillRegistryService(PromptService resources) { this.resources = resources; }

    public String load(String key) {
        var path = skills.get(key);
        if (path == null) throw new IllegalArgumentException("Unknown skill: " + key);
        return resources.load(path);
    }
}
