-- ============================================================
-- IDW QA Phase 4: Update dashboard views for new decision values
-- Run in Supabase SQL Editor (Dashboard > SQL Editor > New query)
-- ============================================================
-- Decision values changed from (approved/rejected/false_positive)
-- to (correct/incorrect/not_applicable). Views must count both
-- old and new values for backward compatibility.
-- ============================================================

-- Drop existing views (safe — these are read-only aggregations)
DROP VIEW IF EXISTS feedback_by_standard;
DROP VIEW IF EXISTS reviewer_activity;

-- ── feedback_by_standard ──
-- Aggregates feedback per standard, mapping old+new decision values
CREATE VIEW feedback_by_standard AS
SELECT
  af.standard_id,
  af.finding_type,
  COUNT(ff.id)                                                  AS total_reviews,
  COUNT(*) FILTER (WHERE ff.decision IN ('correct', 'approved', 'false_positive'))   AS agreed,
  COUNT(*) FILTER (WHERE ff.decision IN ('incorrect', 'rejected'))                   AS disagreed,
  COUNT(*) FILTER (WHERE ff.decision = 'not_applicable')                             AS not_applicable,
  CASE
    WHEN COUNT(ff.id) = 0 THEN 0
    ELSE ROUND(
      COUNT(*) FILTER (WHERE ff.decision IN ('correct', 'approved', 'false_positive'))
      * 100.0 / COUNT(ff.id)
    )
  END                                                           AS agreement_rate
FROM finding_feedback ff
JOIN audit_findings af ON af.id = ff.finding_id
GROUP BY af.standard_id, af.finding_type
ORDER BY agreement_rate ASC;

-- ── reviewer_activity ──
-- Per-reviewer stats with new decision column names
CREATE VIEW reviewer_activity AS
SELECT
  ff.reviewer_name,
  COUNT(ff.id)                                                           AS total_reviews,
  COUNT(*) FILTER (WHERE ff.decision IN ('correct', 'approved', 'false_positive'))   AS agreed,
  COUNT(*) FILTER (WHERE ff.decision IN ('incorrect', 'rejected'))                   AS disagreed,
  COUNT(*) FILTER (WHERE ff.decision = 'not_applicable')                             AS not_applicable,
  MIN(ff.reviewed_at)                                                    AS first_review,
  MAX(ff.reviewed_at)                                                    AS last_review
FROM finding_feedback ff
GROUP BY ff.reviewer_name
ORDER BY total_reviews DESC;
