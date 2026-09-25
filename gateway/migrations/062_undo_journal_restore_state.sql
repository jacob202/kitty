-- Round-2 review finding 5: `undone` cannot mean both "an undo is running"
-- and "the undo finished". Marking the entry undone before `_restore()`
-- completed removed the in-progress newer entry from the conflict guard, so
-- a concurrent older undo restored out of journal order. Journal entries now
-- carry an explicit restore lifecycle: pending -> restoring -> completed.
--
-- The terminal `undone` flag stays authoritative for readers; `state` adds
-- the in-progress step the guard needs. Existing rows backfill from it.

ALTER TABLE undo_journal ADD COLUMN state TEXT NOT NULL DEFAULT 'pending';

UPDATE undo_journal
   SET state = CASE WHEN undone = 1 THEN 'completed' ELSE 'pending' END;
