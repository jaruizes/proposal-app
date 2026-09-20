package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.infrastructure.persistence.entity.PlatformTemplateSettingsJpaEntity;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringPlatformTemplateSettingsRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.Instant;
import java.util.Objects;

@Service
public class TemplateSettingsService {
    public record Settings(String proposalTemplateId,String presentationTemplateId,Instant updatedAt){}
    private static final String GLOBAL="GLOBAL";
    private final SpringPlatformTemplateSettingsRepository repository;
    private final String defaultProposal;
    private final String defaultPresentation;
    public TemplateSettingsService(SpringPlatformTemplateSettingsRepository repository,
        @Value("${proposal-document.template-id:}") String defaultProposal,
        @Value("${presentation.template-id:}") String defaultPresentation){
        this.repository=repository;this.defaultProposal=defaultProposal;this.defaultPresentation=defaultPresentation;
    }
    public Settings get(){
        return repository.findById(GLOBAL)
            .map(e->new Settings(clean(e.getProposalTemplateId()),clean(e.getPresentationTemplateId()),e.getUpdatedAt()))
            .orElse(new Settings(clean(defaultProposal),clean(defaultPresentation),null));
    }
    @Transactional public Settings update(String proposalTemplateId,String presentationTemplateId){
        var e=repository.findById(GLOBAL).orElseGet(PlatformTemplateSettingsJpaEntity::new);
        e.setId(GLOBAL);e.setProposalTemplateId(clean(proposalTemplateId));e.setPresentationTemplateId(clean(presentationTemplateId));e.setUpdatedAt(Instant.now());
        repository.save(e);return new Settings(e.getProposalTemplateId(),e.getPresentationTemplateId(),e.getUpdatedAt());
    }
    private static String clean(String v){return Objects.toString(v,"").trim();}
}
