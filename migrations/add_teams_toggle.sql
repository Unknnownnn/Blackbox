INSERT INTO settings (key, value, value_type, description)
VALUES ('teams_enabled', 'true', 'bool', 'Enable or disable teams feature (for solo competitions)')
ON CONFLICT (key) DO NOTHING;
