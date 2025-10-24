CREATE TABLE IF NOT EXISTS settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `key` VARCHAR(100) NOT NULL UNIQUE,
    value TEXT,
    value_type VARCHAR(20) NOT NULL DEFAULT 'string',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_key (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add is_enabled field to challenges table for temporary disabling
ALTER TABLE challenges 
ADD COLUMN IF NOT EXISTS is_enabled BOOLEAN DEFAULT TRUE 
AFTER is_visible;

-- Insert default CTF control settings
INSERT IGNORE INTO settings (`key`, value, value_type, description) VALUES
('ctf_start_time', NULL, 'datetime', 'CTF start time (UTC)'),
('ctf_end_time', NULL, 'datetime', 'CTF end time (UTC)'),
('is_paused', 'false', 'bool', 'Whether CTF is paused');

-- Add index on challenges.is_enabled for faster queries
CREATE INDEX IF NOT EXISTS idx_challenges_enabled ON challenges(is_enabled);

-- Update existing challenges to be enabled by default (if column was just added)
UPDATE challenges SET is_enabled = TRUE WHERE is_enabled IS NULL;
