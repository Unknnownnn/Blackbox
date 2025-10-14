-- Migration: Add invite_code to teams table and update challenges
-- Date: 2025-10-14
-- Description: 
--   1. Add invite_code column to teams table
--   2. Update max_attempts default value in challenges table
--   3. Generate unique invite codes for existing teams

-- Add invite_code column to teams (temporarily nullable for migration)
ALTER TABLE teams ADD COLUMN invite_code VARCHAR(8) NULL;

-- Create index on invite_code for fast lookups
CREATE INDEX idx_teams_invite_code ON teams(invite_code);

-- Update max_attempts default in challenges table
ALTER TABLE challenges MODIFY COLUMN max_attempts INT DEFAULT 0 COMMENT 'Max attempts per team/user (0=unlimited)';

-- Generate unique invite codes for existing teams
-- Note: This uses a stored procedure to ensure uniqueness
DELIMITER $$

CREATE PROCEDURE generate_team_invite_codes()
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE team_id INT;
    DECLARE new_code VARCHAR(8);
    DECLARE code_exists INT;
    DECLARE cur CURSOR FOR SELECT id FROM teams WHERE invite_code IS NULL;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    OPEN cur;

    read_loop: LOOP
        FETCH cur INTO team_id;
        IF done THEN
            LEAVE read_loop;
        END IF;

        -- Generate unique code
        generate_code: LOOP
            -- Generate random 8-character code
            SET new_code = UPPER(CONCAT(
                CHAR(FLOOR(65 + RAND() * 26)),
                CHAR(FLOOR(65 + RAND() * 26)),
                CHAR(FLOOR(48 + RAND() * 10)),
                CHAR(FLOOR(65 + RAND() * 26)),
                CHAR(FLOOR(48 + RAND() * 10)),
                CHAR(FLOOR(65 + RAND() * 26)),
                CHAR(FLOOR(48 + RAND() * 10)),
                CHAR(FLOOR(65 + RAND() * 26))
            ));

            -- Check if code already exists
            SELECT COUNT(*) INTO code_exists FROM teams WHERE invite_code = new_code;
            
            IF code_exists = 0 THEN
                -- Update team with unique code
                UPDATE teams SET invite_code = new_code WHERE id = team_id;
                LEAVE generate_code;
            END IF;
        END LOOP generate_code;

    END LOOP read_loop;

    CLOSE cur;
END$$

DELIMITER ;

-- Execute the procedure
CALL generate_team_invite_codes();

-- Drop the procedure after use
DROP PROCEDURE generate_team_invite_codes;

-- Make invite_code NOT NULL now that all teams have codes
ALTER TABLE teams MODIFY COLUMN invite_code VARCHAR(8) NOT NULL;

-- Add unique constraint
ALTER TABLE teams ADD UNIQUE KEY unique_invite_code (invite_code);

-- Update challenges with NULL max_attempts to 0 (unlimited)
UPDATE challenges SET max_attempts = 0 WHERE max_attempts IS NULL;

-- Verification queries (optional - comment out in production)
-- SELECT COUNT(*) as teams_with_codes FROM teams WHERE invite_code IS NOT NULL;
-- SELECT COUNT(*) as unique_codes FROM (SELECT DISTINCT invite_code FROM teams) as distinct_codes;
-- SELECT * FROM challenges WHERE max_attempts IS NULL;

-- Commit the changes
COMMIT;
