-- Add hint prerequisites feature
-- Allows hints to require other hints to be unlocked first

-- Add requires_hint_id column to hints table
ALTER TABLE hints 
ADD COLUMN requires_hint_id INT NULL,
ADD CONSTRAINT fk_hint_prerequisite 
    FOREIGN KEY (requires_hint_id) 
    REFERENCES hints(id) 
    ON DELETE SET NULL;

-- Add index for better query performance
CREATE INDEX idx_hints_requires_hint_id ON hints(requires_hint_id);
