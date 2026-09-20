alter table agent_executions add column if not exists checkpoint_key varchar(160);
alter table agent_executions add column if not exists input_fingerprint varchar(64);
alter table agent_executions add column if not exists reused_from_execution_id uuid;
create index if not exists idx_agent_exec_checkpoint on agent_executions(offer_id, phase, checkpoint_key, input_fingerprint, completed_at desc);
