-- Migration: Add teams_enabled toggle setting
-- This allows admins to disable teams for solo competitions

-- Add teams_enabled setting (default true to maintain current behavior)
INSERT INTO settings (key, value, value_type, description)
VALUES ('teams_enabled', 'true', 'bool', 'Enable or disable teams feature (for solo competitions)')
ON CONFLICT (key) DO NOTHING;
