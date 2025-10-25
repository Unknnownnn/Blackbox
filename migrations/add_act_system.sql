-- Add act column if it doesn't exist
ALTER TABLE challenges
ADD COLUMN IF NOT EXISTS act VARCHAR(20) DEFAULT 'ACT I' AFTER category;

-- Create index if it doesn't exist (MySQL will ignore if exists)
CREATE INDEX IF NOT EXISTS idx_challenges_act ON challenges(act);

CREATE TABLE IF NOT EXISTS act_unlocks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    act VARCHAR(20) NOT NULL,
    user_id INT DEFAULT NULL,
    team_id INT DEFAULT NULL,
    unlocked_by_challenge_id INT DEFAULT NULL,
    unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (unlocked_by_challenge_id) REFERENCES challenges(id) ON DELETE SET NULL,
    UNIQUE KEY unique_user_act (user_id, act),
    UNIQUE KEY unique_team_act (team_id, act),
    INDEX idx_act_unlocks_user (user_id),
    INDEX idx_act_unlocks_team (team_id),
    INDEX idx_act_unlocks_act (act)
);

-- Add unlocks_act column if it doesn't exist
ALTER TABLE challenges
ADD COLUMN IF NOT EXISTS unlocks_act VARCHAR(20) DEFAULT NULL AFTER unlock_mode;
