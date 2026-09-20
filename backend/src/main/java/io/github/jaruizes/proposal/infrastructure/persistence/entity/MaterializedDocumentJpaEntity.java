package io.github.jaruizes.proposal.infrastructure.persistence.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="materialized_documents")
public class MaterializedDocumentJpaEntity {
    @Id private UUID id;
    @Column(name="offer_id",nullable=false) private UUID offerId;
    @Column(name="source_artifact_id",nullable=false) private UUID sourceArtifactId;
    @Column(nullable=false) private String type;
    @Column(name="content_version",nullable=false) private int contentVersion;
    @Column(name="render_version",nullable=false) private int renderVersion;
    @Column(name="media_type",nullable=false) private String mediaType;
    @Column(name="file_name",nullable=false) private String fileName;
    @Column(name="template_id",nullable=false) private String templateId;
    @Column(name="renderer_version",nullable=false) private String rendererVersion;
    @Column(name="source_hash",nullable=false,length=64) private String sourceHash;
    @Column(name="render_key",nullable=false,unique=true,length=64) private String renderKey;
    @Column(nullable=false) private String status;
    @Column(name="error_message",columnDefinition="text") private String errorMessage;
    @Lob @Column(columnDefinition="bytea") private byte[] content;
    @Column(name="created_at",nullable=false) private Instant createdAt;
    @Column(name="updated_at",nullable=false) private Instant updatedAt;

    public UUID getId(){return id;} public void setId(UUID v){id=v;}
    public UUID getOfferId(){return offerId;} public void setOfferId(UUID v){offerId=v;}
    public UUID getSourceArtifactId(){return sourceArtifactId;} public void setSourceArtifactId(UUID v){sourceArtifactId=v;}
    public String getType(){return type;} public void setType(String v){type=v;}
    public int getContentVersion(){return contentVersion;} public void setContentVersion(int v){contentVersion=v;}
    public int getRenderVersion(){return renderVersion;} public void setRenderVersion(int v){renderVersion=v;}
    public String getMediaType(){return mediaType;} public void setMediaType(String v){mediaType=v;}
    public String getFileName(){return fileName;} public void setFileName(String v){fileName=v;}
    public String getTemplateId(){return templateId;} public void setTemplateId(String v){templateId=v;}
    public String getRendererVersion(){return rendererVersion;} public void setRendererVersion(String v){rendererVersion=v;}
    public String getSourceHash(){return sourceHash;} public void setSourceHash(String v){sourceHash=v;}
    public String getRenderKey(){return renderKey;} public void setRenderKey(String v){renderKey=v;}
    public String getStatus(){return status;} public void setStatus(String v){status=v;}
    public String getErrorMessage(){return errorMessage;} public void setErrorMessage(String v){errorMessage=v;}
    public byte[] getContent(){return content;} public void setContent(byte[] v){content=v;}
    public Instant getCreatedAt(){return createdAt;} public void setCreatedAt(Instant v){createdAt=v;}
    public Instant getUpdatedAt(){return updatedAt;} public void setUpdatedAt(Instant v){updatedAt=v;}
}
