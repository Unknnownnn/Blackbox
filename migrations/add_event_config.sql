-- CTF Name
INSERT INTO settings (key, value, value_type, description, created_at, updated_at)
VALUES ('ctf_name', 'Capture The Flag', 'string', 'Name of the CTF event', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (key) DO NOTHING;

-- CTF Description
INSERT INTO settings (key, value, value_type, description, created_at, updated_at)
VALUES ('ctf_description', 'Welcome to our CTF platform!', 'string', 'Description of the CTF event', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (key) DO NOTHING;

-- CTF Logo Path
INSERT INTO settings (key, value, value_type, description, created_at, updated_at)
VALUES ('ctf_logo', '', 'string', 'Path to CTF logo image', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (key) DO NOTHING;

-- Allow Registration
INSERT INTO settings (key, value, value_type, description, created_at, updated_at)
VALUES ('allow_registration', 'true', 'bool', 'Allow new user registrations', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (key) DO NOTHING;

-- Team Mode
INSERT INTO settings (key, value, value_type, description, created_at, updated_at)
VALUES ('team_mode', 'true', 'bool', 'Enable team-based CTF mode', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (key) DO NOTHING;
