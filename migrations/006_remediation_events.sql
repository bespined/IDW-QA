-- ============================================================
-- IDW QA: Create remediation_events table
-- Run in Supabase SQL Editor
-- ============================================================
-- Tracks what was fixed, when, how, and by whom.
-- Separate from audit_findings (what AI found) and
-- finding_feedback (human verdicts).
-- ============================================================

CREATE TABLE IF NOT EXISTS remediation_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finding_id UUID REFERENCES audit_findings(id) NOT NULL,
  remediated_by UUID REFERENCES testers(id),
  skill_used TEXT,              -- e.g., 'bulk-edit', 'quiz', 'interactive-content', 'manual'
  description TEXT,             -- e.g., 'Added alt text to 15 images'
  created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: service key full access, anon can read
ALTER TABLE remediation_events ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Service key full access on remediation_events') THEN
    CREATE POLICY "Service key full access on remediation_events" ON remediation_events
      FOR ALL USING (auth.role() = 'service_role');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Anon read remediation_events') THEN
    CREATE POLICY "Anon read remediation_events" ON remediation_events
      FOR SELECT USING (true);
  END IF;
END $$;

-- Index for fast lookups by finding
CREATE INDEX IF NOT EXISTS idx_remediation_events_finding_id ON remediation_events(finding_id);

-- Verify
SELECT 'remediation_events' AS table_name, COUNT(*) AS row_count FROM remediation_events;
