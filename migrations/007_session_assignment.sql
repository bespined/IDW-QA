-- ============================================================
-- IDW QA: Add session assignment for ID Assistant review
-- Run in Supabase SQL Editor
-- ============================================================
-- assigned_to: which ID Assistant is reviewing this session
-- Sticky through rounds — same person reviews all rounds
-- Admin can reassign by updating the field
-- ============================================================

-- Add assigned_to field to audit_sessions
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES testers(id);

-- Ensure audit_purpose has correct values
-- self_audit = new course dev (ID runs audit)
-- recurring = recurring audit (admin runs audit)
-- qa_review = QA review of someone else's work
ALTER TABLE audit_sessions DROP CONSTRAINT IF EXISTS audit_sessions_audit_purpose_check;
ALTER TABLE audit_sessions ADD CONSTRAINT audit_sessions_audit_purpose_check
  CHECK (audit_purpose IS NULL OR audit_purpose IN ('self_audit', 'recurring', 'qa_review'));

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'audit_sessions'
  AND column_name IN ('assigned_to', 'audit_purpose')
ORDER BY column_name;
