create table materialized_documents (
    id uuid primary key,
    offer_id uuid not null references offers(id) on delete cascade,
    source_artifact_id uuid not null references artifacts(id) on delete cascade,
    type varchar(64) not null,
    content_version integer not null,
    render_version integer not null,
    media_type varchar(255) not null,
    file_name varchar(500) not null,
    template_id varchar(255) not null,
    renderer_version varchar(128) not null,
    source_hash varchar(64) not null,
    render_key varchar(64) not null unique,
    status varchar(32) not null,
    error_message text,
    content bytea,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    unique(offer_id,type,render_version)
);
create index idx_materialized_documents_offer on materialized_documents(offer_id,created_at);
create index idx_materialized_documents_source on materialized_documents(source_artifact_id);
