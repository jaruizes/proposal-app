package io.github.jaruizes.proposal.domain.model;

public enum PhaseType {
    ANALYSIS("Entendimiento y cualificación"),
    STRATEGY("Estrategia de respuesta"),
    SOLUTION("Propuesta de solución y plan"),
    PROPOSAL("Documento de oferta detallado"),
    SLIDE_PLAN("Propuesta de presentación"),
    PRESENTATION("Generación de presentación corporativa");
    private final String label;
    PhaseType(String label) { this.label = label; }
    public String label() { return label; }
    public PhaseType next() { return switch (this) {
        case ANALYSIS -> STRATEGY;
        case STRATEGY -> SOLUTION;
        case SOLUTION -> PROPOSAL;
        case PROPOSAL -> SLIDE_PLAN;
        case SLIDE_PLAN -> PRESENTATION;
        case PRESENTATION -> null;
    }; }
}
