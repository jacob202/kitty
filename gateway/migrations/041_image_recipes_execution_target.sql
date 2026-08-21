-- IL-03/IL-04: explicit execution target/model on recipes.
-- Provider name alone cannot identify a FLUX.2 semantic tier (draft vs final);
-- the hosted recipes declare their exact execution target so estimate,
-- availability, dispatch, and observed cost all agree on one target.
ALTER TABLE image_recipes ADD COLUMN execution_target TEXT;