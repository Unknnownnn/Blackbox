-- Migration: add play_sound flag to notifications
ALTER TABLE notifications
ADD COLUMN IF NOT EXISTS play_sound BOOLEAN DEFAULT TRUE;
