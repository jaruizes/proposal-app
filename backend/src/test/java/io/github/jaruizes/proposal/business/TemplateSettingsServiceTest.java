package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.infrastructure.persistence.entity.PlatformTemplateSettingsJpaEntity;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringPlatformTemplateSettingsRepository;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

class TemplateSettingsServiceTest {
    @Test
    void allowsEmptyGlobalTemplates() {
        var repository=mock(SpringPlatformTemplateSettingsRepository.class);
        when(repository.findById("GLOBAL")).thenReturn(Optional.empty());
        var service=new TemplateSettingsService(repository,"","");
        assertThat(service.get().proposalTemplateId()).isEmpty();
        assertThat(service.get().presentationTemplateId()).isEmpty();
    }

    @Test
    void trimsAndPersistsConfiguredTemplates() {
        var repository=mock(SpringPlatformTemplateSettingsRepository.class);
        when(repository.findById("GLOBAL")).thenReturn(Optional.empty());
        when(repository.save(any())).thenAnswer(i->i.getArgument(0));
        var service=new TemplateSettingsService(repository,"","");
        var result=service.update(" corporate-docx "," slides-id ");
        assertThat(result.proposalTemplateId()).isEqualTo("corporate-docx");
        assertThat(result.presentationTemplateId()).isEqualTo("slides-id");
        verify(repository).save(any(PlatformTemplateSettingsJpaEntity.class));
    }
}
