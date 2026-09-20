package io.github.jaruizes.proposal.infrastructure.api.rest;

import io.github.jaruizes.proposal.business.TemplateSettingsService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/settings/templates")
@CrossOrigin(origins="*")
public class TemplateSettingsController {
    private final TemplateSettingsService service;
    public TemplateSettingsController(TemplateSettingsService service){this.service=service;}
    @GetMapping public TemplateSettingsService.Settings get(){return service.get();}
    @PutMapping public TemplateSettingsService.Settings update(@RequestBody UpdateRequest request){
        return service.update(request.proposalTemplateId(),request.presentationTemplateId());
    }
    public record UpdateRequest(String proposalTemplateId,String presentationTemplateId){}
}
