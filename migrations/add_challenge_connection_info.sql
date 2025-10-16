-- Migration: Add connection_info field to challenges table
-- Date: 2025-10-17
-- Description: Add connection_info field for displaying challenge connection details (nc, URLs, etc.)

ALTER TABLE challenges 
ADD COLUMN connection_info VARCHAR(500);
