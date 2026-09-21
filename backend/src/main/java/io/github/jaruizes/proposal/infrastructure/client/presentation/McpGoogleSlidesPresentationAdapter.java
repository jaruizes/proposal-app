package io.github.jaruizes.proposal.infrastructure.client.presentation;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.business.AgentRuntimeService;
import io.github.jaruizes.proposal.business.TemplateSettingsService;
import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.OfferRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.PresentationPort;
import io.github.jaruizes.proposal.domain.ports.ToolGatewayPort;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.*;

/**
 * Google Slides adapter backed by the same Google Workspace MCP server used by proposal-copilot.
 * A configured corporate template is never edited: it is copied first. Without a template,
 * the adapter creates a new blank Google Slides presentation and materializes the approved plan.
 */
@Component
public class McpGoogleSlidesPresentationAdapter implements PresentationPort {
    private static final Set<String> ALLOWED = Set.of(
            "slides_duplicate_slide","slides_delete_slide","slides_move_slides",
            "slides_replace_text","slides_replace_element_text","slides_batch_update");

    private final ToolGatewayPort tools;
    private final AgentRuntimeService agents;
    private final OfferRepositoryPort offers;
    private final ObjectMapper json = new ObjectMapper();
    private final TemplateSettingsService templateSettings;
    private final int maxQaIterations;

    public McpGoogleSlidesPresentationAdapter(ToolGatewayPort tools, AgentRuntimeService agents, OfferRepositoryPort offers,
            TemplateSettingsService templateSettings,
            @Value("${presentation.visual-qa.max-fix-iterations:3}") int maxQaIterations) {
        this.tools=tools; this.agents=agents; this.offers=offers; this.templateSettings=templateSettings; this.maxQaIterations=maxQaIterations;
    }

    @Override
    public PresentationResult materialize(UUID offerId,String slidesPlan,String outputFolder,String documentName) {
        var offer=offers.findById(offerId).orElseThrow(() -> new IllegalStateException("Offer not found"));
        var templateId=presentationId(templateSettings.get().presentationTemplateId());
        var hasTemplate=templateId!=null&&!templateId.isBlank();
        var rawTemplateStructure=hasTemplate?text(tools.execute("slides_get_presentation",Map.of("presentationId",templateId))):"{\"slides\":[],\"layouts\":[],\"masters\":[]}";
        var templateStructure=compactTemplateStructure(rawTemplateStructure);

        // Business Analyst materialization step maps the frozen slide-plan onto the live corporate template.
        var operationPlan=agents.execute(
                AgentTask.of(offerId,PhaseType.PRESENTATION,"business-analyst","generate-presentation",
                        "Plan presentation materialization","""
                        Produce ONLY JSON with this shape: {"operations":[{"tool":"slides_duplicate_slide|slides_delete_slide|slides_move_slides|slides_replace_text|slides_replace_element_text|slides_batch_update","arguments":{...}}]}.
                        Use $PRESENTATION_ID as the presentationId placeholder. Materialize the approved slides-plan exactly: hierarchy, order and exact titles are frozen. Do not rewrite approved narrative copy.
                        The corporate template input is a COMPACT TEMPLATE INVENTORY, not the raw Google Slides API response.
                        Reuse/adapt the listed slide/layout patterns and element identifiers. Do not require omitted style metadata.
                        If the inventory is empty, build a clean presentation from scratch using slides_batch_update createSlide/createShape/insertText requests.
                        Keep operations compact: prefer one slides_batch_update operation with multiple requests over many equivalent operations.
                        """).withOutputFormat("json"),
                model(offer),
                "# APPROVED SLIDES PLAN\n"+slidesPlan+"\n\n# COMPACT CORPORATE TEMPLATE INVENTORY\n"+templateStructure).content();

        var folder=driveId(outputFolder);
        String created;
        if(hasTemplate){
            var copyArgs=new LinkedHashMap<String,Object>();
            copyArgs.put("fileId",templateId); copyArgs.put("newName",documentName);
            if(!folder.isBlank()) copyArgs.put("destinationFolderId",folder);
            created=text(tools.execute("drive_copy_file",copyArgs));
        } else {
            created=text(tools.execute("slides_create_presentation",Map.of("title",documentName)));
        }
        try {
            var node=json.readTree(created); var presentationId=node.path("id").asText(node.path("presentationId").asText());
            if(!hasTemplate&&!folder.isBlank()) tools.execute("drive_move_file",Map.of("fileId",presentationId,"destinationFolderId",folder));
            if(presentationId.isBlank()) throw new IllegalStateException("Presentation creation returned no id: "+created);
            int initialOperations=applyOperations(presentationId,operationPlan);
            int qaOperations=runVisualQa(offer,slidesPlan,presentationId);
            var structure=text(tools.execute("slides_get_presentation",Map.of("presentationId",presentationId)));
            var url="https://docs.google.com/presentation/d/"+presentationId+"/edit";
            var report="""
                    # Presentation build report
                    - Template ID: %s
                    - Rendering mode: %s
                    - Generated presentation ID: %s
                    - Template immutability: original copied before edits
                    - Initial materialization MCP operations: %d
                    - Visual-QA correction operations: %d
                    - Visual-QA max iterations: %d
                    - Final presentation structure fetched: yes
                    - Narrative authority: approved slides-plan.md
                    - Structural hierarchy authority: approved slides-plan.md

                    ## Final structure
                    ```json
                    %s
                    ```
                    """.formatted(hasTemplate?templateId:"none",hasTemplate?"corporate-template":"blank",presentationId,initialOperations,qaOperations,maxQaIterations,structure);
            return new PresentationResult(presentationId,url,report);
        } catch(Exception e){ throw new IllegalStateException("Could not materialize Google Slides presentation",e); }
    }

    private int runVisualQa(Offer offer,String slidesPlan,String presentationId) {
        int corrections=0;
        for(int iteration=1;iteration<=maxQaIterations;iteration++) {
            var inspection=inspectGenerated(presentationId);
            if(inspection.thumbnails().isEmpty()) break;
            var qa=agents.execute(
                    AgentTask.of(offer.id(),PhaseType.PRESENTATION,"business-analyst","generate-presentation",
                            "Visual QA iteration "+iteration,"""
                            Inspect the real slide thumbnails against the frozen slides-plan and current deck structure. Check clipping, overlap, awkward word/syllable wrapping, unreadably dense text, template leftovers, incorrect language and unapproved cliente/customer wording. Do NOT rewrite approved narrative copy.
                            Return ONLY JSON: {"status":"OK|FIX","operations":[...]}. If status is FIX, operations may only use the allowed Slides tools and $PRESENTATION_ID placeholder. Prefer: natural line breaks → textbox geometry → bounded font reduction → alternate corporate pattern. If no safe visual correction remains, return status OK with no operations and describe the unresolved issue in an optional "note" field.
                            """).withOutputFormat("json"),
                    model(offer),
                    "# APPROVED SLIDES PLAN\n"+slidesPlan+"\n\n# CURRENT DECK STRUCTURE\n"+inspection.structure(),
                    inspection.thumbnails()).content();
            try {
                var root=json.readTree(qa);
                if("OK".equalsIgnoreCase(root.path("status").asText())) break;
                var count=applyOperations(presentationId,qa);
                corrections+=count;
                if(count==0) break;
            } catch(Exception e) { break; }
        }
        return corrections;
    }

    private Inspection inspectGenerated(String presentationId) {
        var structure=text(tools.execute("slides_get_presentation",Map.of("presentationId",presentationId)));
        var attachments=new ArrayList<LlmRequest.Attachment>();
        try {
            var root=json.readTree(structure); int count=0;
            for(var slide:root.path("slides")) {
                if(count++>=50) break;
                var slideId=slide.path("objectId").asText(); if(slideId.isBlank())continue;
                var result=tools.execute("slides_get_thumbnail",Map.of("presentationId",presentationId,"slideObjectId",slideId,"size","MEDIUM"));
                @SuppressWarnings("unchecked") var images=(List<Map<String,String>>)result.getOrDefault("images",List.of());
                for(var image:images) {
                    var data=image.get("data"); if(data!=null&&!data.isBlank()) attachments.add(new LlmRequest.Attachment(image.getOrDefault("mimeType","image/png"),data,"slide-"+count+".png"));
                }
            }
        } catch(Exception e){ throw new IllegalStateException("Could not collect slide thumbnails for visual QA",e); }
        return new Inspection(structure,attachments);
    }

    private int applyOperations(String presentationId,String operationPlan) {
        JsonNode root;
        try { root=json.readTree(operationPlan); }
        catch(Exception e){ throw new IllegalArgumentException("Presentation Builder did not return valid JSON operation plan",e); }
        var operations=root.path("operations");
        if(!operations.isArray()) throw new IllegalArgumentException("Presentation operation plan must contain an operations array");
        int count=0;
        for(var op:operations){
            var tool=op.path("tool").asText(); if(!ALLOWED.contains(tool)) throw new IllegalArgumentException("Presentation operation not allowed: "+tool);
            @SuppressWarnings("unchecked") Map<String,Object> args=json.convertValue(op.path("arguments"),Map.class);
            args=replacePresentationId(args,presentationId);
            if(!args.containsKey("presentationId")) args.put("presentationId",presentationId);
            tools.execute(tool,args); count++;
        }
        return count;
    }

    String compactTemplateStructure(String raw) {
        if(raw==null||raw.isBlank()) return "{\"slides\":[],\"layouts\":[],\"masters\":[]}";
        try {
            var root=json.readTree(raw);
            var out=json.createObjectNode();
            out.put("presentationId",root.path("presentationId").asText(""));
            out.put("title",root.path("title").asText(""));

            var slidesOut=out.putArray("slides");
            int slideCount=0;
            for(var slide:root.path("slides")){
                if(slideCount++>=40) break;
                var s=slidesOut.addObject();
                s.put("objectId",slide.path("objectId").asText(""));
                s.put("layoutObjectId",slide.path("slideProperties").path("layoutObjectId").asText(""));
                var elements=s.putArray("elements");
                int elementCount=0;
                for(var element:slide.path("pageElements")){
                    if(elementCount++>=60) break;
                    var e=elements.addObject();
                    e.put("objectId",element.path("objectId").asText(""));
                    if(element.has("shape")){
                        e.put("kind","shape");
                        e.put("shapeType",element.path("shape").path("shapeType").asText(""));
                        e.put("text",compactText(element.path("shape").path("text")));
                    } else if(element.has("image")) {
                        e.put("kind","image");
                    } else if(element.has("table")) {
                        e.put("kind","table");
                    } else if(element.has("line")) {
                        e.put("kind","line");
                    } else {
                        e.put("kind","other");
                    }
                }
            }
            out.put("slideCount",root.path("slides").size());

            var layoutsOut=out.putArray("layouts");
            int layoutCount=0;
            for(var layout:root.path("layouts")){
                if(layoutCount++>=30) break;
                var l=layoutsOut.addObject();
                l.put("objectId",layout.path("objectId").asText(""));
                l.put("name",layout.path("layoutProperties").path("name").asText(""));
                l.put("masterObjectId",layout.path("layoutProperties").path("masterObjectId").asText(""));
            }
            out.put("layoutCount",root.path("layouts").size());

            var mastersOut=out.putArray("masters");
            int masterCount=0;
            for(var master:root.path("masters")){
                if(masterCount++>=10) break;
                var m=mastersOut.addObject();
                m.put("objectId",master.path("objectId").asText(""));
            }
            out.put("masterCount",root.path("masters").size());

            var value=json.writeValueAsString(out);
            // Defensive upper bound: template inventory must remain transport/context metadata,
            // never become a raw document dump. Keep the beginning valid and useful by
            // dropping element detail if an unusually complex template still exceeds 200 KB.
            if(value.length()>200_000){
                for(var slide:slidesOut) ((com.fasterxml.jackson.databind.node.ObjectNode)slide).remove("elements");
                out.put("elementsOmittedForSize",true);
                value=json.writeValueAsString(out);
            }
            return value;
        } catch(Exception e){
            throw new IllegalStateException("Could not compact corporate presentation template structure",e);
        }
    }

    private static String compactText(JsonNode textNode){
        if(textNode==null||textNode.isMissingNode())return "";
        var b=new StringBuilder();
        for(var element:textNode.path("textElements")){
            var value=element.path("textRun").path("content").asText("");
            if(!value.isBlank()) b.append(value);
            if(b.length()>=500)break;
        }
        var text=b.toString().replaceAll("\\s+"," ").trim();
        return text.length()>500?text.substring(0,500):text;
    }

    private String model(Offer offer){return offer.models().getOrDefault("presentation",offer.models().getOrDefault("presentationGeneration","claude-sonnet-4-6"));}
    private Map<String,Object> replacePresentationId(Map<String,Object> source,String id){var result=new LinkedHashMap<String,Object>();source.forEach((k,v)->result.put(k,replace(v,id)));return result;}
    private Object replace(Object value,String id){if(value instanceof String s)return s.replace("$PRESENTATION_ID",id);if(value instanceof Map<?,?> m){var out=new LinkedHashMap<String,Object>();m.forEach((k,v)->out.put(String.valueOf(k),replace(v,id)));return out;}if(value instanceof List<?> l)return l.stream().map(v->replace(v,id)).toList();return value;}
    private static String presentationId(String value){
        var v=Objects.toString(value,"").trim();
        var marker="/presentation/d/";
        var i=v.indexOf(marker);
        if(i>=0){
            var rest=v.substring(i+marker.length());
            var end=rest.indexOf('/');
            if(end<0)end=rest.indexOf('?');
            return end>=0?rest.substring(0,end):rest;
        }
        return v;
    }
    private static String text(Map<String,Object> r){return Objects.toString(r.get("text"),"");}
    private static String driveId(String value){if(value==null)return "";var v=value.trim();var marker="/folders/";var i=v.indexOf(marker);if(i>=0){var x=v.substring(i+marker.length());var q=x.indexOf('?');return q>=0?x.substring(0,q):x;}return v;}
    private record Inspection(String structure,List<LlmRequest.Attachment> thumbnails){}
}
