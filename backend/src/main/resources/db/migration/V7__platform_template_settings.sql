create table platform_template_settings (
    id varchar(64) primary key,
    proposal_template_id varchar(255),
    presentation_template_id varchar(255),
    updated_at timestamptz not null
);
