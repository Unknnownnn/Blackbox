-- Add ACT system for organizing challenges by story acts
-- ACT I, ACT II, ACT III, ACT IV, ACT V

-- Add act column to challenges table
ALTER TABLE challenges
ADD COLUMN act VARCHAR(20) DEFAULT 'ACT I' AFTER category;

-- Add index for better query performance
CREATE INDEX idx_challenges_act ON challenges(act);

-- Add act_unlocks table to track which acts are unlocked for users/teams
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

-- Add unlocks_act field to challenges to specify which act a challenge unlocks
ALTER TABLE challenges
ADD COLUMN unlocks_act VARCHAR(20) DEFAULT NULL AFTER unlock_mode;

-- By default, ACT I is always unlocked for everyone (no entry needed)
-- When a challenge with unlocks_act='ACT II' is solved, ACT II becomes visible
