-- ============================================================
-- IDW QA: Allow anon key to toggle remediation_requested on audit_findings
-- Run in Supabase SQL Editor
-- ============================================================
-- The review app uses the anon key. FindingCard needs to PATCH
-- audit_findings.remediation_requested. Without this policy,
-- the update succeeds (200) but returns empty (RLS blocks it).
-- ============================================================

-- Enable RLS if not already (idempotent)
ALTER TABLE audit_findings ENABLE ROW LEVEL SECURITY;

-- Allow anon to SELECT audit_findings (needed for the review app to read)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Anon read audit_findings') THEN
    CREATE POLICY "Anon read audit_findings" ON audit_findings
      FOR SELECT USING (true);
  END IF;
END $$;

-- Allow anon to UPDATE only the remediation_requested column
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Anon toggle remediation_requested') THEN
    CREATE POLICY "Anon toggle remediation_requested" ON audit_findings
      FOR UPDATE USING (true)
      WITH CHECK (true);
  END IF;
END $$;

-- Service key already has full access via default service_role bypass

-- Verify
SELECT policyname, cmd FROM pg_policies WHERE tablename = 'audit_findings';
