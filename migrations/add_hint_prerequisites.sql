ALTER TABLE hints 
ADD COLUMN requires_hint_id INT NULL,
ADD CONSTRAINT fk_hint_prerequisite 
    FOREIGN KEY (requires_hint_id) 
    REFERENCES hints(id) 
    ON DELETE SET NULL;
    
CREATE INDEX idx_hints_requires_hint_id ON hints(requires_hint_id);
