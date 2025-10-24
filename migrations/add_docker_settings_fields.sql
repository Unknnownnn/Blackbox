ALTER TABLE docker_settings 
ADD COLUMN IF NOT EXISTS max_cpu_percent FLOAT DEFAULT 50.0;

ALTER TABLE docker_settings 
ADD COLUMN IF NOT EXISTS max_memory_mb INT DEFAULT 512;

ALTER TABLE docker_settings 
ADD COLUMN IF NOT EXISTS auto_cleanup_expired BOOLEAN DEFAULT TRUE;

ALTER TABLE docker_settings 
ADD COLUMN IF NOT EXISTS cleanup_interval_minutes INT DEFAULT 5;
