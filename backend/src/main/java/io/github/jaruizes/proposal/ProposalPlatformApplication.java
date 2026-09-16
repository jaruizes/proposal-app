package io.github.jaruizes.proposal;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@EnableAsync
@SpringBootApplication
public class ProposalPlatformApplication {
    public static void main(String[] args) { SpringApplication.run(ProposalPlatformApplication.class, args); }
}
