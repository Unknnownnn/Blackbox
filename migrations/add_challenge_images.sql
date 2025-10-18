-- Add images column to challenges table for displaying images in challenge description
-- Images will be displayed below the description and above connection info

ALTER TABLE challenges 
ADD COLUMN images TEXT NULL COMMENT 'JSON array of image URLs for display';

-- Add is_image flag to challenge_files table to distinguish images from downloadable files
ALTER TABLE challenge_files
ADD COLUMN is_image BOOLEAN DEFAULT FALSE COMMENT 'True if this is an image for display, False if it is a downloadable file';
