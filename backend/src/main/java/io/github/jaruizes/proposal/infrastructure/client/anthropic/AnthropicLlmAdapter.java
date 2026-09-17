package io.github.jaruizes.proposal.infrastructure.client.anthropic;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.LlmProviderPort;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.*;

@Component
public class AnthropicLlmAdapter implements LlmProviderPort {
    private final AnthropicProperties properties;
    private final WebClient webClient;
    public AnthropicLlmAdapter(AnthropicProperties properties, WebClient.Builder builder) {
        this.properties=properties; this.webClient=builder.baseUrl(properties.baseUrl()).build();
    }

    public LlmResult execute(LlmRequest request) {
        if (properties.apiKey()==null || properties.apiKey().isBlank()) {
            if (properties.fallbackToMock()) return mock(request);
            throw new IllegalStateException("ANTHROPIC_API_KEY is required");
        }
        Map<String,Object> payload=new LinkedHashMap<>();
        payload.put("model",request.model()); payload.put("max_tokens",request.maxTokens()); payload.put("system",request.systemPrompt());
        var messages=new ArrayList<Map<String,Object>>();
        for(int i=0;i<request.messages().size();i++){
            var message=request.messages().get(i);
            Object content=message.content();
            if(i==request.messages().size()-1 && "user".equals(message.role()) && !request.attachments().isEmpty()){
                var blocks=new ArrayList<Map<String,Object>>();
                blocks.add(Map.of("type","text","text",message.content()));
                for(var attachment:request.attachments()){
                    if("application/pdf".equals(attachment.mediaType())){
                        blocks.add(Map.of("type","document","source",Map.of("type","base64","media_type",attachment.mediaType(),"data",attachment.base64Data()),"title",attachment.name()));
                    } else if(attachment.mediaType().startsWith("image/")){
                        blocks.add(Map.of("type","image","source",Map.of("type","base64","media_type",attachment.mediaType(),"data",attachment.base64Data())));
                    }
                }
                content=blocks;
            }
            messages.add(Map.of("role",message.role(),"content",content));
        }
        payload.put("messages",messages);
        var response=webClient.post().uri("/v1/messages").contentType(MediaType.APPLICATION_JSON)
                .header("x-api-key",properties.apiKey()).header("anthropic-version",properties.version())
                .bodyValue(payload).retrieve().bodyToMono(JsonNode.class).block();
        if(response==null)throw new IllegalStateException("Empty Anthropic response");
        var text=new StringBuilder();response.path("content").forEach(block->{if("text".equals(block.path("type").asText()))text.append(block.path("text").asText());});
        var usage=response.path("usage");
        return new LlmResult(text.toString(),response.path("model").asText(request.model()),usage.path("input_tokens").asLong(),usage.path("output_tokens").asLong(),response.path("id").asText());
    }

    private LlmResult mock(LlmRequest request){
        var prompt=request.messages().getLast().content();
        String content=prompt.contains("slides-plan")?"# SECTION-01 — Resumen ejecutivo\n\n**Título exacto de sección:** Resumen ejecutivo\n**Portada de sección:** Sí\n\n## SLIDE-001\n\n### Título de slide\nUna propuesta preparada para revisión\n\n### Headline visual opcional\nNo definido\n\n### Objetivo / mensaje principal\nValidar el flujo end-to-end.\n\n### Contenido\n- Ejecución en modo mock por ausencia de API key.\n\n### Soporte visual\n**Tipo:** ninguno\n\n### Notas explicativas\nNo necesarias\n":"# Resultado simulado\n\nANTHROPIC_API_KEY no está configurada. Este artefacto permite validar el workflow local.";
        return new LlmResult(content,request.model(),0,0,"mock-"+UUID.randomUUID());
    }
}
