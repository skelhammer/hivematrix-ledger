-- Fix for feature_options table unique constraint
-- Run this to fix existing database without dropping everything

-- Drop the old unique constraint
ALTER TABLE feature_options DROP CONSTRAINT IF EXISTS feature_options_feature_type_key;

-- Add the correct unique constraint on (feature_type, display_name)
ALTER TABLE feature_options ADD CONSTRAINT unique_feature_option UNIQUE (feature_type, display_name);
