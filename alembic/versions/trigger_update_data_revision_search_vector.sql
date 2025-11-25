-- Trigger function to update the search_vector column on insert or update
CREATE OR REPLACE FUNCTION update_data_revision_search_vector
()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        to_tsvector
('english', coalesce
(NEW.minio_object_key, '') || ' ' || coalesce
(NEW.ai_summary, ''));
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function on insert or update
DROP TRIGGER IF EXISTS trg_update_data_revision_search_vector
ON data_revision;
CREATE TRIGGER trg_update_data_revision_search_vector
BEFORE
INSERT OR
UPDATE ON data_revision
FOR EACH ROW
EXECUTE FUNCTION update_data_revision_search_vector
();


-- CREATE OR REPLACE FUNCTION update_search_vector() 
-- RETURNS trigger AS $$
-- BEGIN
--   NEW.search_vector := to_tsvector('english', 
--     COALESCE(NEW.title, '') || ' ' || 
--     COALESCE(NEW.content, '') || ' ' || 
--     COALESCE(NEW.ai_summary, '')
--   );
--   NEW.updated_at := NOW();
--   RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- -- Create the trigger
-- CREATE TRIGGER data_revision_search_vector_update 
--   BEFORE INSERT OR UPDATE 
--   ON data_revision
--   FOR EACH ROW 
--   EXECUTE FUNCTION update_search_vector();

-- -- Optionally: Backfill existing data
-- UPDATE data_revision 
-- SET search_vector = to_tsvector('english', 
--   COALESCE(title, '') || ' ' || 
--   COALESCE(content, '') || ' ' || 
--   COALESCE(ai_summary, '')
-- )
-- WHERE search_vector IS NULL;