package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.*;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;

@Service
public class ProposalDocumentMaterializationService {
    private static final String CONTRACT_VERSION = "proposal-materializer-v1";
    private static final String DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    private static final String PDF_MEDIA = "application/pdf";

    private final OfferRepositoryPort offers;
    private final ArtifactRepositoryPort artifacts;
    private final MaterializedDocumentRepositoryPort documents;
    private final DocumentPort renderer;
    private final TemplateSettingsService templateSettings;

    public ProposalDocumentMaterializationService(OfferRepositoryPort offers,
                                                  ArtifactRepositoryPort artifacts,
                                                  MaterializedDocumentRepositoryPort documents,
                                                  DocumentPort renderer,
                                                  TemplateSettingsService templateSettings) {
        this.offers=offers;this.artifacts=artifacts;this.documents=documents;this.renderer=renderer;this.templateSettings=templateSettings;
    }

    public List<MaterializedDocument> materializeApprovedProposal(UUID offerId) {
        var offer=offers.findById(offerId).orElseThrow(()->new DomainException("Offer not found"));
        var proposal=artifacts.findLatest(offerId,ArtifactType.PROPOSAL)
                .orElseThrow(()->new DomainException("Missing canonical proposal.md"));
        var sourceHash=sha256(proposal.content());
        String rendererVersion;
        try { rendererVersion=renderer.rendererVersion(); }
        catch(Exception e) { rendererVersion="unavailable"; }
        var template=templateSettings.get().proposalTemplateId();

        var request=new DocumentRenderRequest(
                offerId,proposal.content(),offer.name(),offer.language(),template,
                Map.of(
                        "sourceArtifactId",proposal.id().toString(),
                        "contentVersion",proposal.version(),
                        "sourceHash",sourceHash,
                        "materializerVersion",CONTRACT_VERSION));

        var results=new ArrayList<MaterializedDocument>();
        results.add(materializeOne(offer,proposal,request,ArtifactType.PROPOSAL_DOCX,DOCX_MEDIA,rendererVersion,sourceHash));
        results.add(materializeOne(offer,proposal,request,ArtifactType.PROPOSAL_PDF,PDF_MEDIA,rendererVersion,sourceHash));
        return results;
    }

    public List<MaterializedDocument> list(UUID offerId){return documents.findByOfferId(offerId);}

    public MaterializedDocument find(UUID offerId,UUID documentId){
        var item=documents.findById(documentId).orElseThrow(()->new DomainException("Materialized document not found"));
        if(!item.offerId().equals(offerId))throw new DomainException("Materialized document does not belong to offer");
        return item;
    }

    private MaterializedDocument materializeOne(Offer offer,Artifact proposal,DocumentRenderRequest request,
                                                ArtifactType type,String mediaType,String rendererVersion,String sourceHash) {
        var renderKey=sha256(String.join("|",sourceHash,request.templateId(),rendererVersion,CONTRACT_VERSION,type.name()));
        var existing=documents.findByRenderKey(renderKey);
        if(existing.isPresent() && existing.get().status()==DocumentMaterializationStatus.READY)return existing.get();
        if(existing.isPresent() && existing.get().status()==DocumentMaterializationStatus.PROCESSING)return existing.get();

        var now=Instant.now();
        var processing=existing.orElseGet(()->new MaterializedDocument(
                UUID.randomUUID(),offer.id(),proposal.id(),type,proposal.version(),
                documents.nextRenderVersion(offer.id(),type),mediaType,fileName(type,proposal.version()),
                request.templateId(),rendererVersion,sourceHash,renderKey,DocumentMaterializationStatus.PROCESSING,
                null,null,now,now));
        processing=new MaterializedDocument(processing.id(),processing.offerId(),processing.sourceArtifactId(),processing.type(),
                processing.contentVersion(),processing.renderVersion(),processing.mediaType(),processing.fileName(),
                request.templateId(),rendererVersion,sourceHash,renderKey,DocumentMaterializationStatus.PROCESSING,
                null,null,processing.createdAt(),now);
        documents.save(processing);

        try {
            var rendered=type==ArtifactType.PROPOSAL_DOCX?renderer.renderProposalDocx(request):renderer.renderMarkdownPdf(request);
            var ready=new MaterializedDocument(processing.id(),processing.offerId(),processing.sourceArtifactId(),processing.type(),
                    processing.contentVersion(),processing.renderVersion(),rendered.mediaType(),fileName(type,proposal.version()),
                    rendered.templateId(),rendered.rendererVersion(),sourceHash,renderKey,DocumentMaterializationStatus.READY,
                    null,rendered.content(),processing.createdAt(),Instant.now());
            return documents.save(ready);
        } catch(Exception e) {
            var failed=new MaterializedDocument(processing.id(),processing.offerId(),processing.sourceArtifactId(),processing.type(),
                    processing.contentVersion(),processing.renderVersion(),mediaType,fileName(type,proposal.version()),
                    request.templateId(),rendererVersion,sourceHash,renderKey,DocumentMaterializationStatus.FAILED,
                    concise(e),null,processing.createdAt(),Instant.now());
            return documents.save(failed);
        }
    }

    private static String fileName(ArtifactType type,int contentVersion){
        var suffix=contentVersion>1?"-v"+contentVersion:"";
        return type==ArtifactType.PROPOSAL_DOCX?"proposal"+suffix+".docx":"proposal"+suffix+".pdf";
    }

    private static String concise(Exception e){
        var value=e.getMessage();
        if(value==null||value.isBlank())value=e.getClass().getSimpleName();
        return value.length()>2000?value.substring(0,2000):value;
    }

    static String sha256(String value){
        try{
            return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        }catch(Exception e){throw new IllegalStateException("Cannot calculate document hash",e);}
    }
}
