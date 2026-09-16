package io.github.jaruizes.proposal.domain.model;

public enum PhaseType {
    ANALYSIS("Entendimiento y cualificación"), STRATEGY("Estrategia de respuesta"), SOLUTION("Definición de solución"), SLIDE_PLAN("Planificación narrativa"), PRESENTATION("Presentación corporativa");
    private final String label;
    PhaseType(String label) { this.label = label; }
    public String label() { return label; }
    public PhaseType next() { return switch (this) { case ANALYSIS -> STRATEGY; case STRATEGY -> SOLUTION; case SOLUTION -> SLIDE_PLAN; case SLIDE_PLAN -> PRESENTATION; case PRESENTATION -> null; }; }
}
