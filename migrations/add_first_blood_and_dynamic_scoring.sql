-- Add is_first_blood column to solves table
ALTER TABLE solves 
ADD COLUMN is_first_blood BOOLEAN DEFAULT FALSE AFTER points_earned;

-- Make user_id nullable in solves (for manual adjustments)
ALTER TABLE solves 
MODIFY COLUMN user_id INT NULL;

-- Make challenge_id nullable in solves (for manual adjustments)
ALTER TABLE solves 
MODIFY COLUMN challenge_id INT NULL;

-- Add first_blood_bonus setting (default 0 = disabled)
INSERT INTO settings (key, value, value_type, description)
VALUES ('first_blood_bonus', '0', 'int', 'Bonus points awarded for first blood (first solve of a challenge). Set to 0 to disable.')
ON CONFLICT (key) DO NOTHING;

-- Update existing solves to mark first bloods
UPDATE solves s1
SET is_first_blood = TRUE
WHERE s1.challenge_id IS NOT NULL
AND s1.solved_at = (
    SELECT MIN(s2.solved_at)
    FROM solves s2
    WHERE s2.challenge_id = s1.challenge_id
    AND s2.challenge_id IS NOT NULL
);
