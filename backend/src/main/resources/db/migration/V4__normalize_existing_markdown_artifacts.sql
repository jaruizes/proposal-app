-- Repair documents published before the Agent Platform enforced output format.
do $$
declare
    artifact_row record;
    document text;
    filename text;
    body text;
    newline_at integer;
begin
    for artifact_row in
        select id, content from artifacts
        where type in ('OPPORTUNITY_BRIEF', 'QUESTIONS', 'TECHNOLOGY', 'STRATEGY',
                       'SOLUTION', 'SOLUTION_PLAN', 'PROPOSAL', 'SLIDES_PLAN')
    loop
        document := btrim(artifact_row.content);
        filename := split_part(document, E'\n', 1);
        if filename ~ '^# [A-Za-z0-9][A-Za-z0-9._-]*[.]md$' then
            document := btrim(substr(document, length(filename) + 2));
        end if;
        newline_at := strpos(document, E'\n');
        if newline_at > 0
           and split_part(document, E'\n', 1) in ('```markdown', '```md', '```')
           and right(document, 4) = E'\n```' then
            body := btrim(substr(document, newline_at + 1, length(document) - newline_at - 4));
            if body like '# %' and strpos(body, E'\n') > 0 then
                update artifacts set content = body where id = artifact_row.id;
            end if;
        end if;
    end loop;
end $$;
