package io.github.jaruizes.proposal.infrastructure.persistence.entity;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name="platform_template_settings")
public class PlatformTemplateSettingsJpaEntity {
    @Id private String id;
    @Column(name="proposal_template_id") private String proposalTemplateId;
    @Column(name="presentation_template_id") private String presentationTemplateId;
    @Column(name="updated_at",nullable=false) private Instant updatedAt;
    public String getId(){return id;} public void setId(String v){id=v;}
    public String getProposalTemplateId(){return proposalTemplateId;} public void setProposalTemplateId(String v){proposalTemplateId=v;}
    public String getPresentationTemplateId(){return presentationTemplateId;} public void setPresentationTemplateId(String v){presentationTemplateId=v;}
    public Instant getUpdatedAt(){return updatedAt;} public void setUpdatedAt(Instant v){updatedAt=v;}
}
