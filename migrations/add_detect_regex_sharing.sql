ALTER TABLE challenges
ADD COLUMN detect_regex_sharing BOOLEAN DEFAULT FALSE AFTER docker_flag_path;

-- Optional: index to quickly find challenges with detection enabled
CREATE INDEX IF NOT EXISTS idx_challenge_detect_regex_sharing ON challenges(detect_regex_sharing);
