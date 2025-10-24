ALTER TABLE challenges 
ADD COLUMN images TEXT NULL COMMENT 'JSON array of image URLs for display';

ALTER TABLE challenge_files
ADD COLUMN is_image BOOLEAN DEFAULT FALSE COMMENT 'True if this is an image for display, False if it is a downloadable file';
