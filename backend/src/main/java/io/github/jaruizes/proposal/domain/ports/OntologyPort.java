package io.github.jaruizes.proposal.domain.ports;
import java.util.Map;
public interface OntologyPort { Map<String,Object> query(String expression); }
