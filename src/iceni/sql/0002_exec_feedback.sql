-- Phase III — consumer-success feedback signals per execution.
-- The calibration objective is downstream-consumer success (parse fidelity +
-- acceptance + low edit distance), NOT output style. Style is only the lever;
-- these columns are the objective function (GPT + Kimi, unanimous).
ALTER TABLE executions ADD COLUMN parse_ok INTEGER;  -- 1/0: output parsed in the model's target shape
ALTER TABLE executions ADD COLUMN quality  REAL;     -- optional V1/judge score 0-100 when available
