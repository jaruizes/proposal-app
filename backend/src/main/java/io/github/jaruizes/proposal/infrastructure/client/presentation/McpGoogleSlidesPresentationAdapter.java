package io.github.jaruizes.proposal.infrastructure.client.presentation;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.domain.model.LlmRequest;
import io.github.jaruizes.proposal.domain.ports.PresentationPort;
import io.github.jaruizes.proposal.domain.ports.ToolGatewayPort;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class McpGoogleSlidesPresentationAdapter implements PresentationPort {
    private static final Set<String> ALLOWED = Set.of(
            "slides_duplicate_slide","slides_delete_slide","slides_move_slides",
            "slides_replace_text","slides_replace_element_text","slides_batch_update");
    private final ToolGatewayPort tools;
    private final ObjectMapper json = new ObjectMapper();
    private final String templateId;

    public McpGoogleSlidesPresentationAdapter(ToolGatewayPort tools,
            @Value("${presentation.template-id:}") String templateId) {
        this.tools=tools; this.templateId=templateId;
    }

    @Override
    public String inspectTemplate() {
        requireTemplate();
        return text(tools.execute("slides_get_presentation",Map.of("presentationId",templateId)));
    }

    @Override
    public PresentationResult materialize(UUID offerId,String slidesPlan,String outputFolder,String documentName,String operationPlan) {
        requireTemplate();
        var copyArgs=new LinkedHashMap<String,Object>();
        copyArgs.put("fileId",templateId); copyArgs.put("newName",documentName);
        var folder=driveId(outputFolder); if(!folder.isBlank()) copyArgs.put("destinationFolderId",folder);
        var copy=text(tools.execute("drive_copy_file",copyArgs));
        try {
            var node=json.readTree(copy); var presentationId=node.path("id").asText();
            if(presentationId.isBlank()) throw new IllegalStateException("Google Drive copy returned no id: "+copy);
            applyOperations(presentationId,operationPlan);
            var structure=text(tools.execute("slides_get_presentation",Map.of("presentationId",presentationId)));
            var operationCount=countOperations(operationPlan);
            var url="https://docs.google.com/presentation/d/"+presentationId+"/edit";
            var report="""
                    # Presentation build report
                    - Template ID: %s
                    - Generated presentation ID: %s
                    - Template immutability: original copied before edits
                    - Planned MCP operations applied: %d
                    - Final presentation structure fetched: yes
                    - Narrative authority: approved slides-plan.md

                    Visual QA is executed by the Presentation Builder after this materialization using real slide thumbnails.
                    """.formatted(templateId,presentationId,operationCount);
            return new PresentationResult(presentationId,url,report+"\n\n## Final structure\n```json\n"+structure+"\n```");
        } catch(Exception e){ throw new IllegalStateException("Could not materialize Google Slides presentation",e); }
    }

    @Override
    public PresentationInspection inspectGenerated(String presentationId) {
        var structure=text(tools.execute("slides_get_presentation",Map.of("presentationId",presentationId)));
        var attachments=new ArrayList<LlmRequest.Attachment>();
        try {
            var root=json.readTree(structure); int count=0;
            for(var slide:root.path("slides")) {
                if(count++>=50) break;
                var slideId=slide.path("objectId").asText(); if(slideId.isBlank())continue;
                var result=tools.execute("slides_get_thumbnail",Map.of("presentationId",presentationId,"slideObjectId",slideId,"size","MEDIUM"));
                @SuppressWarnings("unchecked") var images=(List<Map<String,String>>)result.getOrDefault("images",List.of());
                for(var image:images) attachments.add(new LlmRequest.Attachment(image.getOrDefault("mimeType","image/png"),image.get("data"),"slide-"+count+".png"));
            }
        } catch(Exception e){ throw new IllegalStateException("Could not collect slide thumbnails for visual QA",e); }
        return new PresentationInspection(structure,attachments);
    }

    @Override
    public void applyOperations(String presentationId,String operationPlan) {
        JsonNode root;
        try { root=json.readTree(stripFences(operationPlan)); }
        catch(Exception e){ throw new IllegalArgumentException("Presentation Builder did not return valid JSON operation plan",e); }
        var operations=root.path("operations");
        if(!operations.isArray()) throw new IllegalArgumentException("Presentation operation plan must contain an operations array");
        for(var op:operations){
            var tool=op.path("tool").asText(); if(!ALLOWED.contains(tool)) throw new IllegalArgumentException("Presentation operation not allowed: "+tool);
            @SuppressWarnings("unchecked") Map<String,Object> args=json.convertValue(op.path("arguments"),Map.class);
            args=replacePresentationId(args,presentationId);
            if(!args.containsKey("presentationId")) args.put("presentationId",presentationId);
            tools.execute(tool,args);
        }
    }

    private Map<String,Object> replacePresentationId(Map<String,Object> source,String id){var result=new LinkedHashMap<String,Object>();source.forEach((k,v)->result.put(k,replace(v,id)));return result;}
    private Object replace(Object value,String id){
        if(value instanceof String s)return s.replace("$PRESENTATION_ID",id);
        if(value instanceof Map<?,?> m){var out=new LinkedHashMap<String,Object>();m.forEach((k,v)->out.put(String.valueOf(k),replace(v,id)));return out;}
        if(value instanceof List<?> l)return l.stream().map(v->replace(v,id)).toList();
        return value;
    }
    private int countOperations(String raw){try{return json.readTree(stripFences(raw)).path("operations").size();}catch(Exception e){return 0;}}
    private void requireTemplate(){if(templateId==null||templateId.isBlank())throw new IllegalStateException("GOOGLE_SLIDES_TEMPLATE_ID/presentation.template-id is required for phase 5");}
    private static String text(Map<String,Object> r){return Objects.toString(r.get("text"),"");}
    private static String stripFences(String raw){var s=raw.trim();if(s.startsWith("```")){var first=s.indexOf('\n');var last=s.lastIndexOf("```");if(first>=0&&last>first)s=s.substring(first+1,last).trim();}return s;}
    private static String driveId(String value){if(value==null)return "";var v=value.trim();var marker="/folders/";var i=v.indexOf(marker);if(i>=0){var x=v.substring(i+marker.length());var q=x.indexOf('?');return q>=0?x.substring(0,q):x;}return v;}
}
