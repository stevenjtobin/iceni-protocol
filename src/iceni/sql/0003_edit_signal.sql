-- Phase III — persist the raw edit signal (GPT: keep components, not just the aggregate).
-- parse_fit and acceptance are recomputable from parse_ok + outcome, so outcome_score
-- stays computed-on-read and the weights remain re-tunable against full history. The
-- edit distance is the one component with no recompute path, so it must be stored.
ALTER TABLE executions ADD COLUMN edit_distance REAL;  -- 0=kept verbatim, 1=rewritten; null=unknown
