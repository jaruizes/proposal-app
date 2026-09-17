package io.github.jaruizes.proposal.infrastructure.api.rest.mapper;

import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.infrastructure.api.rest.dto.OfferResponse;
import java.util.*;

public final class OfferRestMapper {
    private static final Set<ArtifactType> INTERNAL_ARTIFACTS = EnumSet.of(
            ArtifactType.SOURCE_MANIFEST,
            ArtifactType.SOURCE_CONTEXT,
            ArtifactType.SOURCE_INGESTION_REPORT);

    private OfferRestMapper() {}

    public static OfferResponse toResponse(Offer o,List<PhaseExecution> phases,List<Artifact> artifacts){
        var byPhase=new EnumMap<PhaseType,StringBuilder>(PhaseType.class);
        for(var a:artifacts){
            if(INTERNAL_ARTIFACTS.contains(a.type())) continue;
            byPhase.computeIfAbsent(a.phase(),ignored->new StringBuilder())
                    .append("\n\n# ").append(a.type()).append(" · v").append(a.version()).append("\n\n").append(a.content());
        }
        var prs=phases.stream().sorted(Comparator.comparingInt(p->p.phase().ordinal()))
                .map(p->new OfferResponse.PhaseResponse(key(p.phase()),p.phase().label(),phaseStatus(p.status()),
                        Optional.ofNullable(byPhase.get(p.phase())).map(StringBuilder::toString).orElse(null))).toList();
        return new OfferResponse(o.id(),o.name(),o.customer(),o.presentationLanguage(),o.inputDriveFolder(),o.outputDriveFolder(),
                o.presentationName(),o.aiProvider(),o.models(),o.presentationGuidance(),o.currentPhase().label(),overall(o.status()),o.createdAt(),prs);
    }
    private static String key(PhaseType p){return switch(p){case ANALYSIS->"analysis";case STRATEGY->"strategy";case SOLUTION->"solution";case SLIDE_PLAN->"slide-plan";case PRESENTATION->"presentation";};}
    private static String phaseStatus(ExecutionStatus s){return switch(s){case RUNNING->"working";case WAITING_FOR_HUMAN->"waiting_approval";case APPROVED->"approved";case CANCELLED->"cancelled";case FAILED->"failed";case STALE,INVALIDATED->"stale";default->"pending";};}
    private static String overall(ExecutionStatus s){return switch(s){case RUNNING->"Trabajando";case WAITING_FOR_HUMAN->"Esperando aprobación";case CANCELLED->"Cancelado";case APPROVED->"Completado";case FAILED->"Error";default->"Pendiente";};}
}
