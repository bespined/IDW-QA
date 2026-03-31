-- ============================================================
-- IDW QA: Update finding_feedback decision values
-- Run in Supabase SQL Editor
-- ============================================================

-- Drop old CHECK constraint on decision column
ALTER TABLE finding_feedback DROP CONSTRAINT IF EXISTS finding_feedback_decision_check;

-- Add new constraint allowing both old and new values (backward compatible)
ALTER TABLE finding_feedback ADD CONSTRAINT finding_feedback_decision_check
  CHECK (decision IN ('approved', 'rejected', 'false_positive', 'correct', 'incorrect', 'not_applicable'));

-- Verify
SELECT DISTINCT decision FROM finding_feedback;
