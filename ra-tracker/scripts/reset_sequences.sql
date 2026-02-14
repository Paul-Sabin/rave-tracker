-- Reset PostgreSQL sequences after data migration from SQLite.
-- Run this after pgloader or migrate_sqlite_to_pg.py if sequences are out of sync.
--
-- Usage: psql -d your_database -f scripts/reset_sequences.sql

SELECT setval('rules_id_seq', COALESCE((SELECT MAX(id) FROM rules), 1));
SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1));
SELECT setval('notifications_id_seq', COALESCE((SELECT MAX(id) FROM notifications), 1));
SELECT setval('audit_logs_id_seq', COALESCE((SELECT MAX(id) FROM audit_logs), 1));

-- Verify: show current sequence values
SELECT 'rules_id_seq' as sequence, last_value FROM rules_id_seq;
SELECT 'users_id_seq' as sequence, last_value FROM users_id_seq;
SELECT 'notifications_id_seq' as sequence, last_value FROM notifications_id_seq;
SELECT 'audit_logs_id_seq' as sequence, last_value FROM audit_logs_id_seq;
