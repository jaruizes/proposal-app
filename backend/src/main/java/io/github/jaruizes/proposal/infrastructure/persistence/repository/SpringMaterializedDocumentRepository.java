package io.github.jaruizes.proposal.infrastructure.persistence.repository;

import io.github.jaruizes.proposal.infrastructure.persistence.entity.MaterializedDocumentJpaEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.*;

public interface SpringMaterializedDocumentRepository extends JpaRepository<MaterializedDocumentJpaEntity,UUID> {
    List<MaterializedDocumentJpaEntity> findByOfferIdOrderByCreatedAtAsc(UUID offerId);
    Optional<MaterializedDocumentJpaEntity> findByRenderKey(String renderKey);
    long countByOfferIdAndType(UUID offerId,String type);
}
