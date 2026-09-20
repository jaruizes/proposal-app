package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.*;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

import static org.assertj.core.api.Assertions.assertThat;

class ProposalDocumentMaterializationServiceTest {

    @Test
    void materializesDocxAndPdfAndReusesSameRenderKey() {
        var offerId=UUID.randomUUID();
        var sourceId=UUID.randomUUID();
        var offer=new Offer(offerId,"Acme Proposal","Acme","es","es","in","out","Deck","slides","builtin-neutral",
                "ANTHROPIC",Map.of(),Map.of(),Map.of(),PhaseType.PROPOSAL,ExecutionStatus.APPROVED,Instant.now(),Instant.now());
        var proposal=new Artifact(sourceId,offerId,PhaseType.PROPOSAL,ArtifactType.PROPOSAL,1,"# Proposal\n\nBody",Instant.now());

        var docs=new InMemoryDocuments();
        var renderer=new FakeRenderer();
        var service=new ProposalDocumentMaterializationService(
                new SingleOfferRepo(offer),new SingleArtifactRepo(proposal),docs,renderer);

        var first=service.materializeApprovedProposal(offerId);
        var second=service.materializeApprovedProposal(offerId);

        assertThat(first).hasSize(2);
        assertThat(first).allMatch(d->d.status()==DocumentMaterializationStatus.READY);
        assertThat(second).extracting(MaterializedDocument::id).containsExactlyElementsOf(first.stream().map(MaterializedDocument::id).toList());
        assertThat(renderer.docxCalls).isEqualTo(1);
        assertThat(renderer.pdfCalls).isEqualTo(1);
        assertThat(docs.items).hasSize(2);
    }

    @Test
    void recordsPdfFailureWithoutLosingReadyDocx() {
        var offerId=UUID.randomUUID();
        var sourceId=UUID.randomUUID();
        var offer=new Offer(offerId,"Acme Proposal","Acme","es","es","in","out","Deck","slides","builtin-neutral",
                "ANTHROPIC",Map.of(),Map.of(),Map.of(),PhaseType.PROPOSAL,ExecutionStatus.APPROVED,Instant.now(),Instant.now());
        var proposal=new Artifact(sourceId,offerId,PhaseType.PROPOSAL,ArtifactType.PROPOSAL,2,"# Proposal\n\nBody v2",Instant.now());

        var docs=new InMemoryDocuments();
        var renderer=new FakeRenderer();renderer.failPdf=true;
        var service=new ProposalDocumentMaterializationService(
                new SingleOfferRepo(offer),new SingleArtifactRepo(proposal),docs,renderer);

        var result=service.materializeApprovedProposal(offerId);

        assertThat(result).extracting(MaterializedDocument::status)
                .containsExactly(DocumentMaterializationStatus.READY,DocumentMaterializationStatus.FAILED);
        assertThat(result.get(0).content()).isNotEmpty();
        assertThat(result.get(1).content()).isNull();
        assertThat(result.get(1).errorMessage()).contains("pdf failed");
    }

    static class FakeRenderer implements DocumentPort {
        int docxCalls; int pdfCalls; boolean failPdf;
        public String rendererVersion(){return "renderer-test-v1";}
        public RenderedDocument renderProposalDocx(DocumentRenderRequest r){docxCalls++;return new RenderedDocument("docx".getBytes(),"application/vnd.openxmlformats-officedocument.wordprocessingml.document","proposal.docx",r.templateId(),"renderer-test-v1");}
        public RenderedDocument renderMarkdownPdf(DocumentRenderRequest r){pdfCalls++;if(failPdf)throw new IllegalStateException("pdf failed");return new RenderedDocument("pdf".getBytes(),"application/pdf","proposal.pdf",r.templateId(),"renderer-test-v1");}
    }

    static class InMemoryDocuments implements MaterializedDocumentRepositoryPort {
        final Map<UUID,MaterializedDocument> items=new LinkedHashMap<>();
        public MaterializedDocument save(MaterializedDocument d){items.put(d.id(),d);return d;}
        public List<MaterializedDocument> findByOfferId(UUID id){return items.values().stream().filter(d->d.offerId().equals(id)).toList();}
        public Optional<MaterializedDocument> findById(UUID id){return Optional.ofNullable(items.get(id));}
        public Optional<MaterializedDocument> findByRenderKey(String key){return items.values().stream().filter(d->d.renderKey().equals(key)).findFirst();}
        public int nextRenderVersion(UUID offerId,ArtifactType type){return (int)items.values().stream().filter(d->d.offerId().equals(offerId)&&d.type()==type).count()+1;}
    }

    record SingleOfferRepo(Offer offer) implements OfferRepositoryPort {
        public Offer save(Offer o){return o;} public Optional<Offer> findById(UUID id){return offer.id().equals(id)?Optional.of(offer):Optional.empty();} public List<Offer> findAll(){return List.of(offer);}
    }

    record SingleArtifactRepo(Artifact artifact) implements ArtifactRepositoryPort {
        public Artifact save(Artifact a){return a;} public List<Artifact> findByOfferId(UUID id){return artifact.offerId().equals(id)?List.of(artifact):List.of();}
        public Optional<Artifact> findLatest(UUID offerId,ArtifactType type){return artifact.offerId().equals(offerId)&&artifact.type()==type?Optional.of(artifact):Optional.empty();}
        public int nextVersion(UUID offerId,ArtifactType type){return 2;}
    }
}
