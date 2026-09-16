package io.github.jaruizes.proposal.domain.ports;
import java.util.Map;
public interface ToolGatewayPort { Map<String,Object> execute(String toolName, Map<String,Object> arguments); }
