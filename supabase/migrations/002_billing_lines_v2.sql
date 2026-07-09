-- VoltFlow V2 — billing lines with dynamic pricing metadata
-- Run on the same Supabase project as GreenOps (after 001_subscriptions.sql).

alter table public.billing_lines
  add column if not exists kwh numeric(12, 3),
  add column if not exists duration_hours numeric(8, 3),
  add column if not exists unit_price_cents integer,
  add column if not exists pricing_source text,
  add column if not exists carbon_gco2_kwh numeric(8, 2),
  add column if not exists hp_hc_band text;

comment on column public.billing_lines.pricing_source is
  'gridpulse_carbon | slot_score_fallback | stub_fallback';

-- One billing line per flex_slot (idempotent usage recording).
create unique index if not exists billing_lines_flex_slot_unique
  on public.billing_lines (flex_slot_id)
  where flex_slot_id is not null;
