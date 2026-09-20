alter table offers add column if not exists proposal_template_id varchar(255);
update offers set proposal_template_id='builtin-neutral' where proposal_template_id is null or btrim(proposal_template_id)='';
alter table offers alter column proposal_template_id set default 'builtin-neutral';
