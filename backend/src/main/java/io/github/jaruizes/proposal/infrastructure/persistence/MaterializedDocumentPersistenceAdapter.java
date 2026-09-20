package io.github.jaruizes.proposal.infrastructure.persistence;

import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.MaterializedDocumentRepositoryPort;
import io.github.jaruizes.proposal.infrastructure.persistence.entity.MaterializedDocumentJpaEntity;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringMaterializedDocumentRepository;
import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class MaterializedDocumentPersistenceAdapter implements MaterializedDocumentRepositoryPort {
    private final SpringMaterializedDocumentRepository repository;
    public MaterializedDocumentPersistenceAdapter(SpringMaterializedDocumentRepository repository){this.repository=repository;}

    @Override public MaterializedDocument save(MaterializedDocument d){return toDomain(repository.save(toEntity(d)));}
    @Override public List<MaterializedDocument> findByOfferId(UUID offerId){return repository.findByOfferIdOrderByCreatedAtAsc(offerId).stream().map(MaterializedDocumentPersistenceAdapter::toDomain).toList();}
    @Override public Optional<MaterializedDocument> findById(UUID id){return repository.findById(id).map(MaterializedDocumentPersistenceAdapter::toDomain);}
    @Override public Optional<MaterializedDocument> findByRenderKey(String renderKey){return repository.findByRenderKey(renderKey).map(MaterializedDocumentPersistenceAdapter::toDomain);}
    @Override public int nextRenderVersion(UUID offerId,ArtifactType type){return (int)repository.countByOfferIdAndType(offerId,type.name())+1;}

    private static MaterializedDocumentJpaEntity toEntity(MaterializedDocument d){
        var e=new MaterializedDocumentJpaEntity();
        e.setId(d.id());e.setOfferId(d.offerId());e.setSourceArtifactId(d.sourceArtifactId());e.setType(d.type().name());
        e.setContentVersion(d.contentVersion());e.setRenderVersion(d.renderVersion());e.setMediaType(d.mediaType());e.setFileName(d.fileName());
        e.setTemplateId(d.templateId());e.setRendererVersion(d.rendererVersion());e.setSourceHash(d.sourceHash());e.setRenderKey(d.renderKey());
        e.setStatus(d.status().name());e.setErrorMessage(d.errorMessage());e.setContent(d.content());e.setCreatedAt(d.createdAt());e.setUpdatedAt(d.updatedAt());
        return e;
    }
    private static MaterializedDocument toDomain(MaterializedDocumentJpaEntity e){
        return new MaterializedDocument(e.getId(),e.getOfferId(),e.getSourceArtifactId(),ArtifactType.valueOf(e.getType()),
                e.getContentVersion(),e.getRenderVersion(),e.getMediaType(),e.getFileName(),e.getTemplateId(),e.getRendererVersion(),
                e.getSourceHash(),e.getRenderKey(),DocumentMaterializationStatus.valueOf(e.getStatus()),e.getErrorMessage(),e.getContent(),e.getCreatedAt(),e.getUpdatedAt());
    }
}
