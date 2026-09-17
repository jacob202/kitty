-- 061 — One running retry child per parent run, enforced by the ledger itself.
-- retry_run writes the parent claim and its child in one transaction, so the
-- claim can no longer outlive a dispatch that never happened; this index keeps
-- any other writer from opening a second concurrent retry of the same run.
--
-- A database written before the index existed can already hold two running
-- children for one parent, which would fail the index build. Keep the newest
-- attempt and close the older duplicate first so those databases still migrate.
UPDATE automation_runs
   SET status = 'interrupted',
       completed_at = COALESCE(completed_at, started_at),
       error = COALESCE(error, 'Superseded by a concurrent retry of the same run')
 WHERE status = 'running'
   AND retry_of_run_id IS NOT NULL
   AND EXISTS (
       SELECT 1
         FROM automation_runs AS winner
        WHERE winner.retry_of_run_id = automation_runs.retry_of_run_id
          AND winner.status = 'running'
          AND (winner.started_at, winner.id) > (automation_runs.started_at, automation_runs.id)
   );

CREATE UNIQUE INDEX IF NOT EXISTS idx_automation_runs_one_running_retry
    ON automation_runs (retry_of_run_id)
    WHERE status = 'running' AND retry_of_run_id IS NOT NULL;
