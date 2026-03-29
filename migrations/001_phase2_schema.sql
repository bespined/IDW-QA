-- ============================================================
-- IDW QA Phase 2: Supabase Schema Migration
-- Run this in the Supabase SQL Editor (Dashboard > SQL Editor > New query)
-- Safe to run multiple times — all statements use IF NOT EXISTS
-- ============================================================

-- ============================================================
-- PART A: New tables (create these first — other steps reference them)
-- ============================================================

-- Testers: stores all pilot users (IDs, IDAs, QA team, admins)
CREATE TABLE IF NOT EXISTS testers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  email TEXT UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('id', 'id_assistant', 'qa_team', 'admin')),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Tester course assignments: which IDAs are assigned to which courses
CREATE TABLE IF NOT EXISTS tester_course_assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tester_id UUID REFERENCES testers(id) NOT NULL,
  course_id TEXT NOT NULL,
  course_name TEXT,
  canvas_domain TEXT,
  assigned_by UUID REFERENCES testers(id),
  assigned_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  status TEXT DEFAULT 'assigned' CHECK (status IN ('assigned', 'in_progress', 'completed'))
);

-- Error reports: bug/issue tracking from plugin users
CREATE TABLE IF NOT EXISTS error_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reported_by UUID REFERENCES testers(id),
  error_type TEXT NOT NULL CHECK (error_type IN ('bug', 'wrong_finding', 'crash', 'other')),
  description TEXT NOT NULL,
  context JSONB,
  status TEXT DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
  resolved_by UUID REFERENCES testers(id),
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- PART B: Add new columns to existing tables
-- ============================================================

-- audit_sessions: workflow tracking fields
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS audit_purpose TEXT DEFAULT 'self_audit';
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS audit_round INTEGER DEFAULT 1;
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS previous_session_id UUID;
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'in_progress';
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS submitted_by UUID;
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS launch_gate_approved BOOLEAN DEFAULT false;
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS launch_gate_approved_by UUID;
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS launch_gate_approved_at TIMESTAMPTZ;
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS airtable_synced_at TIMESTAMPTZ;
ALTER TABLE audit_sessions ADD COLUMN IF NOT EXISTS plugin_version TEXT;

-- audit_findings: reviewer tier and evidence fields
ALTER TABLE audit_findings ADD COLUMN IF NOT EXISTS reviewer_tier TEXT DEFAULT 'id';
ALTER TABLE audit_findings ADD COLUMN IF NOT EXISTS canvas_link TEXT;
ALTER TABLE audit_findings ADD COLUMN IF NOT EXISTS page_slug TEXT;
ALTER TABLE audit_findings ADD COLUMN IF NOT EXISTS module_id INTEGER;
ALTER TABLE audit_findings ADD COLUMN IF NOT EXISTS criterion_id TEXT;
ALTER TABLE audit_findings ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'design_standard';
ALTER TABLE audit_findings ADD COLUMN IF NOT EXISTS remediation_requested BOOLEAN DEFAULT false;

-- finding_feedback: override tracking and corrected findings
ALTER TABLE finding_feedback ADD COLUMN IF NOT EXISTS corrected_finding TEXT;
ALTER TABLE finding_feedback ADD COLUMN IF NOT EXISTS correction_note TEXT;
ALTER TABLE finding_feedback ADD COLUMN IF NOT EXISTS reviewer_tier TEXT;
ALTER TABLE finding_feedback ADD COLUMN IF NOT EXISTS original_decision TEXT;
ALTER TABLE finding_feedback ADD COLUMN IF NOT EXISTS overridden_by UUID;
ALTER TABLE finding_feedback ADD COLUMN IF NOT EXISTS overridden_at TIMESTAMPTZ;
ALTER TABLE finding_feedback ADD COLUMN IF NOT EXISTS override_reason TEXT;

-- ============================================================
-- PART C: Foreign key constraints (audit_sessions -> testers)
-- ============================================================

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audit_sessions_submitted_by_fkey') THEN
    ALTER TABLE audit_sessions ADD CONSTRAINT audit_sessions_submitted_by_fkey
      FOREIGN KEY (submitted_by) REFERENCES testers(id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'audit_sessions_launch_gate_approved_by_fkey') THEN
    ALTER TABLE audit_sessions ADD CONSTRAINT audit_sessions_launch_gate_approved_by_fkey
      FOREIGN KEY (launch_gate_approved_by) REFERENCES testers(id);
  END IF;
END $$;

-- ============================================================
-- PART D: RLS policies for pilot security
-- ============================================================

ALTER TABLE testers ENABLE ROW LEVEL SECURITY;
ALTER TABLE tester_course_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE error_reports ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Service key full access on testers') THEN
    CREATE POLICY "Service key full access on testers" ON testers FOR ALL USING (auth.role() = 'service_role');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Service key full access on tester_course_assignments') THEN
    CREATE POLICY "Service key full access on tester_course_assignments" ON tester_course_assignments FOR ALL USING (auth.role() = 'service_role');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Service key full access on error_reports') THEN
    CREATE POLICY "Service key full access on error_reports" ON error_reports FOR ALL USING (auth.role() = 'service_role');
  END IF;
END $$;

-- ============================================================
-- PART E: Verification (run after migration to confirm)
-- ============================================================

SELECT 'NEW TABLES' as check_type, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('testers', 'tester_course_assignments', 'error_reports')
ORDER BY table_name;

SELECT 'AUDIT_SESSIONS COLUMNS' as check_type, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'audit_sessions'
  AND column_name IN ('audit_purpose', 'audit_round', 'status', 'plugin_version', 'launch_gate_approved')
ORDER BY column_name;

SELECT 'AUDIT_FINDINGS COLUMNS' as check_type, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'audit_findings'
  AND column_name IN ('reviewer_tier', 'canvas_link', 'criterion_id', 'category', 'remediation_requested')
ORDER BY column_name;

SELECT 'FINDING_FEEDBACK COLUMNS' as check_type, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'finding_feedback'
  AND column_name IN ('corrected_finding', 'correction_note', 'original_decision', 'overridden_by', 'override_reason')
ORDER BY column_name;
