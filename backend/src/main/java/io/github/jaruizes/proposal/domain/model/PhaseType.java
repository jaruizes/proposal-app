package io.github.jaruizes.proposal.domain.model;

public enum PhaseType {
    ANALYSIS("Entendimiento y calificación"),
    SOLUTION("Propuesta de solución y plan de delivery"),
    PROPOSAL("Documento de oferta"),
    SLIDE_PLAN("Hilo de presentación"),
    PRESENTATION("Generación de presentación");

    private final String label;
    PhaseType(String label) { this.label = label; }
    public String label() { return label; }

    public PhaseType next() { return switch (this) {
        case ANALYSIS -> SOLUTION;
        case SOLUTION -> PROPOSAL;
        case PROPOSAL -> SLIDE_PLAN;
        case SLIDE_PLAN -> PRESENTATION;
        case PRESENTATION -> null;
    }; }
}
