package io.github.jaruizes.proposal.infrastructure.client.presentation;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.business.AgentRuntimeService;
import io.github.jaruizes.proposal.business.TemplateSettingsService;
import io.github.jaruizes.proposal.domain.ports.OfferRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.ToolGatewayPort;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

class McpGoogleSlidesPresentationAdapterTest {

    @Test
    void compactsLargeGoogleSlidesStructureBeforeAgentTransport() throws Exception {
        var adapter=new McpGoogleSlidesPresentationAdapter(
                mock(ToolGatewayPort.class),
                mock(AgentRuntimeService.class),
                mock(OfferRepositoryPort.class),
                mock(TemplateSettingsService.class),
                0);

        var json=new ObjectMapper();
        var root=json.createObjectNode();
        root.put("presentationId","template-1");
        root.put("title","Corporate");
        var slides=root.putArray("slides");
        for(int s=0;s<20;s++){
            var slide=slides.addObject();
            slide.put("objectId","slide-"+s);
            slide.putObject("slideProperties").put("layoutObjectId","layout-"+(s%3));
            var elements=slide.putArray("pageElements");
            for(int e=0;e<20;e++){
                var element=elements.addObject();
                element.put("objectId","element-"+s+"-"+e);
                var shape=element.putObject("shape");
                shape.put("shapeType","TEXT_BOX");
                var text=shape.putObject("text").putArray("textElements").addObject();
                text.putObject("textRun").put("content","Placeholder "+e+" "+"x".repeat(4000));
                // Representative heavy Google API fields that should never reach NATS.
                element.put("heavyStyleBlob","y".repeat(4000));
            }
        }
        var layouts=root.putArray("layouts");
        for(int i=0;i<3;i++){
            var layout=layouts.addObject();
            layout.put("objectId","layout-"+i);
            layout.putObject("layoutProperties").put("name","Layout "+i).put("masterObjectId","master-1");
        }
        root.putArray("masters").addObject().put("objectId","master-1");

        var raw=json.writeValueAsString(root);
        assertThat(raw.length()).isGreaterThan(1_000_000);

        var compact=adapter.compactTemplateStructure(raw);

        assertThat(compact.length()).isLessThan(200_000);
        assertThat(compact).contains("template-1","slide-0","element-0-0","layout-0");
        assertThat(compact).doesNotContain("heavyStyleBlob");
    }
}
