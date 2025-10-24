ALTER TABLE challenge_flags 
ADD COLUMN is_regex BOOLEAN DEFAULT FALSE AFTER is_case_sensitive;

CREATE INDEX IF NOT EXISTS idx_flag_abuse_timestamp ON flag_abuse_attempts(timestamp);

CREATE INDEX IF NOT EXISTS idx_flag_abuse_team ON flag_abuse_attempts(team_id);

ALTER TABLE challenge_flags 
MODIFY COLUMN flag_value VARCHAR(500);