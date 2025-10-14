-- Migration: Add Challenge Branching and Prerequisites
-- Created: 2025-10-14
-- Description: Adds support for multiple flags per challenge, flag-based branching, and challenge prerequisites

-- Table for multiple flags per challenge
CREATE TABLE IF NOT EXISTS challenge_flags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    challenge_id INT NOT NULL,
    flag_value VARCHAR(255) NOT NULL,
    flag_label VARCHAR(100),  -- e.g., "Path A", "Secret Route", etc.
    unlocks_challenge_id INT,  -- Challenge that gets unlocked when this flag is submitted
    is_case_sensitive BOOLEAN DEFAULT TRUE,
    points_override INT,  -- Override points for this specific flag (NULL = use default)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
    FOREIGN KEY (unlocks_challenge_id) REFERENCES challenges(id) ON DELETE SET NULL,
    INDEX idx_challenge_flags_challenge (challenge_id),
    INDEX idx_challenge_flags_unlocks (unlocks_challenge_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table for challenge prerequisites
CREATE TABLE IF NOT EXISTS challenge_prerequisites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    challenge_id INT NOT NULL,  -- The challenge that requires prerequisites
    prerequisite_challenge_id INT NOT NULL,  -- The challenge that must be solved first
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
    FOREIGN KEY (prerequisite_challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
    UNIQUE KEY unique_prerequisite (challenge_id, prerequisite_challenge_id),
    INDEX idx_challenge_prereq_challenge (challenge_id),
    INDEX idx_challenge_prereq_prereq (prerequisite_challenge_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table to track which flags were used to unlock which challenges
CREATE TABLE IF NOT EXISTS challenge_unlocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    team_id INT,
    challenge_id INT NOT NULL,  -- The challenge that was unlocked
    unlocked_by_flag_id INT NOT NULL,  -- The flag that unlocked it
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
    FOREIGN KEY (unlocked_by_flag_id) REFERENCES challenge_flags(id) ON DELETE CASCADE,
    UNIQUE KEY unique_unlock (user_id, team_id, challenge_id),
    INDEX idx_unlocks_user (user_id),
    INDEX idx_unlocks_team (team_id),
    INDEX idx_unlocks_challenge (challenge_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add columns to challenges table to indicate if challenge is hidden by default
-- Check if column exists before adding (idempotent migration)
SET @dbname = DATABASE();
SET @tablename = 'challenges';
SET @columnname = 'is_hidden';
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE (table_name = @tablename)
    AND (table_schema = @dbname)
    AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  'ALTER TABLE challenges ADD COLUMN is_hidden BOOLEAN DEFAULT FALSE AFTER is_visible'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

SET @columnname = 'unlock_mode';
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE (table_name = @tablename)
    AND (table_schema = @dbname)
    AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  'ALTER TABLE challenges ADD COLUMN unlock_mode VARCHAR(20) DEFAULT ''none'' AFTER is_hidden'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;
-- unlock_mode: 'none' = always visible, 'prerequisite' = requires prerequisites, 'flag_unlock' = requires flag from another challenge

-- Add column to track which flag was submitted for a solve
SET @tablename = 'solves';
SET @columnname = 'flag_id';
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE (table_name = @tablename)
    AND (table_schema = @dbname)
    AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  'ALTER TABLE solves ADD COLUMN flag_id INT AFTER challenge_id'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add foreign key if it doesn't exist
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
  WHERE CONSTRAINT_SCHEMA = @dbname
  AND TABLE_NAME = 'solves'
  AND CONSTRAINT_NAME = 'solves_ibfk_flag'
  AND CONSTRAINT_TYPE = 'FOREIGN KEY');

SET @preparedStatement = IF(@fk_exists > 0,
  'SELECT 1',
  'ALTER TABLE solves ADD CONSTRAINT solves_ibfk_flag FOREIGN KEY (flag_id) REFERENCES challenge_flags(id) ON DELETE SET NULL'
);
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Migrate existing challenges: create challenge_flags entry for each existing challenge
INSERT INTO challenge_flags (challenge_id, flag_value, flag_label, is_case_sensitive)
SELECT id, flag, 'Default Flag', flag_case_sensitive
FROM challenges
WHERE flag IS NOT NULL AND flag != '';

-- Optional: Can remove old flag column after migration
-- ALTER TABLE challenges DROP COLUMN flag;
-- ALTER TABLE challenges DROP COLUMN flag_case_sensitive;
