-- V9: Publication-attempt provenance — actor identity and an optional
-- caller-supplied attempt key on every detection run so a lost publication
-- response can be reconciled against bounded attempt history.
ALTER TABLE grid_detection_run
    ADD COLUMN actor text,
    ADD COLUMN request_key text;
