-- ============================================================
-- IDW QA: Change requests table
-- Run in Supabase SQL Editor
-- ============================================================
-- When IDA syncs to Airtable, their session is locked.
-- If they need a change, they submit a request here.
-- Admin sees a queue and can act on it.
-- ============================================================

CREATE TABLE IF NOT EXISTS change_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES audit_sessions(id) NOT NULL,
  finding_id UUID REFERENCES audit_findings(id),
  requested_by UUID REFERENCES testers(id),
  reason TEXT NOT NULL,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'resolved', 'dismissed')),
  resolved_by UUID REFERENCES testers(id),
  resolution_note TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

ALTER TABLE change_requests ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Service key full access on change_requests') THEN
    CREATE POLICY "Service key full access on change_requests" ON change_requests FOR ALL USING (auth.role() = 'service_role');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Anon read change_requests') THEN
    CREATE POLICY "Anon read change_requests" ON change_requests FOR SELECT USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Anon insert change_requests') THEN
    CREATE POLICY "Anon insert change_requests" ON change_requests FOR INSERT WITH CHECK (true);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_change_requests_session ON change_requests(session_id);
CREATE INDEX IF NOT EXISTS idx_change_requests_status ON change_requests(status);

SELECT 'change_requests' AS table_name, COUNT(*) AS row_count FROM change_requests;
