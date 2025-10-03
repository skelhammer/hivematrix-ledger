-- Add Datto Backup Data Puller to scheduler_jobs
-- Run this if you already have the database initialized

INSERT INTO scheduler_jobs (
    job_name,
    script_path,
    schedule_cron,
    description,
    enabled
) VALUES (
    'Sync Backup Data from Datto RMM',
    'sync_backup_data_from_datto.py',
    '0 2 * * *',
    'Pulls backup storage data from Datto RMM UDF fields for backup billing',
    false
) ON CONFLICT (job_name) DO NOTHING;
