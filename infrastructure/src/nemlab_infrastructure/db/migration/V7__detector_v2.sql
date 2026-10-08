-- V7: detector v2 — three new event types and a per-event evidence payload.
--
-- `detail` carries immutable event-specific evidence (reversal trough/peak,
-- episode member ranges, ramp baseline manifest). It is NOT detector config:
-- parameters stay in detector_params, revisions in source_revisions.

ALTER TABLE grid_event DROP CONSTRAINT grid_event_type_check;
ALTER TABLE grid_event
    ADD CONSTRAINT grid_event_type_check CHECK (type IN (
        'negative_price_run','price_spike','demand_ramp',
        'unusual_demand_ramp','price_reversal','negative_price_episode'));
ALTER TABLE grid_event ADD COLUMN detail jsonb;
