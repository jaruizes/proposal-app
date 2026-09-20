package io.github.jaruizes.proposal.infrastructure.persistence.repository;
import io.github.jaruizes.proposal.infrastructure.persistence.entity.PlatformTemplateSettingsJpaEntity;
import org.springframework.data.jpa.repository.JpaRepository;
public interface SpringPlatformTemplateSettingsRepository extends JpaRepository<PlatformTemplateSettingsJpaEntity,String> {}
