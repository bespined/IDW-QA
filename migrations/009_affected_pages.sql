-- IDW QA: Add affected_pages JSONB column to audit_findings
-- Stores structured per-page evidence: slug, title, url, issue_summary, issue_count
-- Used by the review app to show direct Canvas page links instead of generic module links

ALTER TABLE audit_findings ADD COLUMN IF NOT EXISTS affected_pages JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN audit_findings.affected_pages IS 'Structured per-page evidence: [{slug, title, url, issue_summary, issue_count}]';
