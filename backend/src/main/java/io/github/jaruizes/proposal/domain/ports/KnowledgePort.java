package io.github.jaruizes.proposal.domain.ports;
import java.util.List;
public interface KnowledgePort { List<String> search(String scope, String query, int limit); }
