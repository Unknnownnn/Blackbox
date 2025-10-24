ALTER TABLE challenges 
ADD COLUMN IF NOT EXISTS requires_team BOOLEAN DEFAULT FALSE 
AFTER is_enabled;

-- Create hints table
CREATE TABLE IF NOT EXISTS hints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    challenge_id INT NOT NULL,
    content TEXT NOT NULL,
    cost INT NOT NULL DEFAULT 0,
    `order` INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (challenge_id) REFERENCES challenges(id) ON DELETE CASCADE,
    INDEX idx_challenge_id (challenge_id),
    INDEX idx_order (`order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create hint_unlocks table to track which hints users/teams have unlocked
CREATE TABLE IF NOT EXISTS hint_unlocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hint_id INT NOT NULL,
    user_id INT NOT NULL,
    team_id INT DEFAULT NULL,
    cost_paid INT NOT NULL,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hint_id) REFERENCES hints(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    INDEX idx_hint_user (hint_id, user_id),
    INDEX idx_hint_team (hint_id, team_id),
    UNIQUE KEY unique_hint_user (hint_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add global setting for requiring teams (set during setup)
INSERT IGNORE INTO settings (`key`, value, value_type, description) VALUES
('require_team_for_challenges', 'false', 'bool', 'Require users to be in a team to solve challenges');

-- Update existing challenges to not require teams by default
UPDATE challenges SET requires_team = FALSE WHERE requires_team IS NULL;
