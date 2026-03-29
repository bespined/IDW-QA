-- ============================================================
-- IDW QA: Merge qa_team role into admin
-- Run in Supabase SQL Editor
-- ============================================================

-- Step 1: Update any existing qa_team users to admin
UPDATE testers SET role = 'admin' WHERE role = 'qa_team';

-- Step 2: Drop the old CHECK constraint and add new one
ALTER TABLE testers DROP CONSTRAINT IF EXISTS testers_role_check;
ALTER TABLE testers ADD CONSTRAINT testers_role_check CHECK (role IN ('id', 'id_assistant', 'admin'));

-- Verify
SELECT id, name, role FROM testers ORDER BY role, name;
