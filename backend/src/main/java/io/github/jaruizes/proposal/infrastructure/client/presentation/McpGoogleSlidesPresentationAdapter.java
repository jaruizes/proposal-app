package io.github.jaruizes.proposal.infrastructure.client.presentation;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.business.AgentRuntimeService;
import io.github.jaruizes.proposal.business.TemplateSettingsService;
import io.github.jaruizes.proposal.domain.model.*;
import io.github.jaruizes.proposal.domain.ports.OfferRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.PresentationPort;
import io.github.jaruizes.proposal.domain.ports.ToolGatewayPort;
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

    public McpGoogleSlidesPresentationAdapter(ToolGatewayPort tools, AgentRuntimeService agents, OfferRepositoryPort offers,
            TemplateSettingsService templateSettings) {
        this.tools=tools; this.agents=agents; this.offers=offers; this.templateSettings=templateSettings;
    }

    @Override
    public PresentationResult materialize(UUID offerId,String slidesPlan,String outputFolder,String documentName) {
        var offer=offers.findById(offerId).orElseThrow(() -> new IllegalStateException("Offer not found"));
        var templateId=presentationId(templateSettings.get().presentationTemplateId());
        var hasTemplate=templateId!=null&&!templateId.isBlank();
        var rawTemplateStructure=hasTemplate?text(tools.execute("slides_get_presentation",Map.of("presentationId",templateId))):"{\"slides\":[],\"layouts\":[],\"masters\":[]}";
        var templateStructure=compactTemplateStructure(rawTemplateStructure);

        // Materialization is planned in bounded, checkpointable chunks. NATS still carries
        // the same process-agnostic AgentExecution command; only the application chooses
        // several small executions instead of one giant JSON response.
        var slideChunks=splitSlidesPlan(slidesPlan,4);
        var operationPlans=new ArrayList<String>();
        for(int i=0;i<slideChunks.size();i++){
            var chunk=slideChunks.get(i);
            var checkpoint="presentation.materialization.chunk."+(i+1);
            var operationPlan=agents.execute(
                    AgentTask.of(offerId,PhaseType.PRESENTATION,"business-analyst","generate-presentation",
                            "Plan presentation materialization chunk "+(i+1)+" of "+slideChunks.size(),"""
                            Produce ONLY JSON with this shape:
                            {"operations":[{"tool":"slides_duplicate_slide|slides_delete_slide|slides_move_slides|slides_replace_text|slides_replace_element_text|slides_batch_update","arguments":{...}}]}.

                            Use $PRESENTATION_ID as the presentationId placeholder.
                            Materialize ONLY the supplied slides-plan chunk. The global slide IDs/order and exact titles are frozen.
                            Do not plan or modify slides outside this chunk, except when a referenced corporate-template slide must
                            be duplicated as the basis for one slide in this chunk. Never delete or reorder slides belonging to
                            another chunk. Do not rewrite approved narrative copy.

                            The corporate template input is a COMPACT TEMPLATE INVENTORY, not the raw Google Slides API response.
                            Reuse/adapt listed layouts/elements when useful. If no suitable template pattern exists, use
                            slides_batch_update createSlide/createShape/insertText requests.

                            Keep the operation payload bounded. Prefer one slides_batch_update with multiple requests where safe.
                            Do not include explanations, markdown or operations for any other chunk.
                            """).withOutputFormat("json").withCheckpoint(checkpoint),
                    model(offer),
                    "# PRESENTATION GLOBAL OUTLINE\n"+slidesPlanOutline(slidesPlan)
                            +"\n\n# CURRENT SLIDES-PLAN CHUNK\n"+chunk
                            +"\n\n# COMPACT CORPORATE TEMPLATE INVENTORY\n"+templateStructure).content();
            operationPlans.add(operationPlan);
        }

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
            int initialOperations=0;
            for(var operationPlan:operationPlans) initialOperations+=applyOperations(presentationId,operationPlan);
            var structure=text(tools.execute("slides_get_presentation",Map.of("presentationId",presentationId)));
            var structuralQa=structuralQaReport(slidesPlan,structure);
            var url="https://docs.google.com/presentation/d/"+presentationId+"/edit";
            var report="""
                    # Presentation build report
                    - Template ID: %s
                    - Rendering mode: %s
                    - Generated presentation ID: %s
                    - Template immutability: original copied before edits
                    - Initial materialization MCP operations: %d
                    - Structural-QA mode: deterministic post-build inspection
                    - Structural-QA result: %s
                    - Final presentation structure fetched: yes
                    - Narrative authority: approved slides-plan.md
                    - Structural hierarchy authority: approved slides-plan.md

                    ## Final structure
                    ```json
                    %s
                    ```
                    """.formatted(hasTemplate?templateId:"none",hasTemplate?"corporate-template":"blank",presentationId,initialOperations,structuralQa,structure);
            return new PresentationResult(presentationId,url,report);
        } catch(Exception e){ throw new IllegalStateException("Could not materialize Google Slides presentation",e); }
    }

    private String structuralQaReport(String slidesPlan,String structure){
        try{
            var expected=slidesPlan==null?0:(int)Arrays.stream(slidesPlan.split("\\R"))
                    .filter(line->line.startsWith("## SLIDE-")).count();
            var root=json.readTree(structure==null?"{}":structure);
            var actual=root.path("slides").isArray()?root.path("slides").size():0;
            var leftovers=new ArrayList<String>();
            if(root.path("slides").isArray()){
                for(var slide:root.path("slides")){
                    for(var element:slide.path("pageElements")){
                        if(!element.has("shape"))continue;
                        var text=compactText(element.path("shape").path("text"));
                        var lower=text.toLowerCase(Locale.ROOT);
                        if(lower.contains("lorem ipsum")||lower.contains("placeholder")||lower.contains("insert text"))
                            leftovers.add(text);
                    }
                }
            }
            if(actual!=expected)
                return "WARN expectedSlides="+expected+", actualSlides="+actual+", templateLeftovers="+leftovers.size();
            if(!leftovers.isEmpty())
                return "WARN templateLeftovers="+leftovers.size();
            return "OK expectedSlides="+expected+", actualSlides="+actual;
        }catch(Exception e){
            return "WARN structural inspection unavailable: "+e.getMessage();
        }
    }

    private String compactDeckStructure(String raw){
        if(raw==null||raw.isBlank())return "{}";
        try{
            var root=json.readTree(raw);
            var out=json.createObjectNode();
            var slidesOut=out.putArray("slides");
            int count=0;
            for(var slide:root.path("slides")){
                if(count++>=50)break;
                var s=slidesOut.addObject();
                s.put("objectId",slide.path("objectId").asText(""));
                var texts=s.putArray("texts");
                for(var element:slide.path("pageElements")){
                    if(!element.has("shape"))continue;
                    var text=compactText(element.path("shape").path("text"));
                    if(!text.isBlank())texts.add(text);
                }
            }
            out.put("slideCount",root.path("slides").size());
            return json.writeValueAsString(out);
        }catch(Exception e){
            throw new IllegalStateException("Could not compact generated deck structure for QA",e);
        }
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

    List<String> splitSlidesPlan(String slidesPlan,int maxSlidesPerChunk){
        if(slidesPlan==null||slidesPlan.isBlank())return List.of("");
        var lines=slidesPlan.split("\\R",-1);
        var chunks=new ArrayList<String>();
        var header=new StringBuilder();
        var current=new StringBuilder();
        int currentSlides=0;
        boolean seenSlide=false;

        for(var line:lines){
            if(line.startsWith("## SLIDE-")){
                if(currentSlides>=maxSlidesPerChunk && current.length()>0){
                    chunks.add(current.toString().trim());
                    current.setLength(0);
                    currentSlides=0;
                }
                currentSlides++;
                seenSlide=true;
            }
            if(!seenSlide){
                header.append(line).append('\n');
            }else{
                current.append(line).append('\n');
            }
        }
        if(current.length()>0)chunks.add(current.toString().trim());
        if(chunks.isEmpty())chunks.add(slidesPlan.trim());

        var prefix=header.toString().trim();
        if(!prefix.isBlank()){
            for(int i=0;i<chunks.size();i++) chunks.set(i,prefix+"\n\n"+chunks.get(i));
        }
        return List.copyOf(chunks);
    }

    String slidesPlanOutline(String slidesPlan){
        if(slidesPlan==null||slidesPlan.isBlank())return "";
        var out=new StringBuilder();
        for(var line:slidesPlan.split("\\R")){
            if(line.startsWith("# ")||line.startsWith("## SLIDE-")){
                out.append(line).append('\n');
            }
        }
        var value=out.toString().trim();
        return value.length()>12_000?value.substring(0,12_000):value;
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
                    if(elementCount++>=12) break;
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
            if(b.length()>=180)break;
        }
        var text=b.toString().replaceAll("\\s+"," ").trim();
        return text.length()>180?text.substring(0,180):text;
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
