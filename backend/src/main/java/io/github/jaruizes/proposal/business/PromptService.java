package io.github.jaruizes.proposal.business;
import org.springframework.core.io.ClassPathResource; import org.springframework.stereotype.Service; import java.nio.charset.StandardCharsets;
@Service public class PromptService { public String load(String resource){try(var in=new ClassPathResource(resource).getInputStream()){return new String(in.readAllBytes(),StandardCharsets.UTF_8);}catch(Exception e){throw new IllegalStateException("Cannot load prompt "+resource,e);}} }
