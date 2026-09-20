-- Rename the delivery artifact type introduced originally as SOLUTION_PLAN.
-- Keep existing offers readable after the domain enum is renamed to DELIVERY_PLAN.
UPDATE artifacts
SET type = 'DELIVERY_PLAN'
WHERE type = 'SOLUTION_PLAN';
