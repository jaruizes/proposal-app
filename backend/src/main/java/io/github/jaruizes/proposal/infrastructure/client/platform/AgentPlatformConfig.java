package io.github.jaruizes.proposal.infrastructure.client.platform;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(AgentPlatformProperties.class)
public class AgentPlatformConfig {}
