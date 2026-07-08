-- VoltFlow V1 — subscriptions + billing_lines
--
-- IMPORTANT: this migration runs on the SAME Supabase project as GreenOps/FlexSlot,
-- NOT a dedicated VoltFlow project. It depends on objects created by GreenOps'
-- own migrations (public.organizations, public.flex_slots, public.user_org_ids()).
-- Apply GreenOps' migrations first if bootstrapping a fresh project.

create table public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null unique references public.organizations (id) on delete cascade,
  stripe_customer_id text,
  stripe_subscription_id text,
  plan text not null default 'free' check (plan in ('free', 'pro')),
  status text not null default 'none',
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index subscriptions_org_id_idx on public.subscriptions (org_id);
create index subscriptions_stripe_customer_id_idx on public.subscriptions (stripe_customer_id);

create table public.billing_lines (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations (id) on delete cascade,
  flex_slot_id uuid references public.flex_slots (id) on delete set null,
  amount_cents integer not null default 0,
  stripe_invoice_item_id text,
  created_at timestamptz not null default now()
);

create index billing_lines_org_id_idx on public.billing_lines (org_id);
create index billing_lines_flex_slot_id_idx on public.billing_lines (flex_slot_id);

-- RLS: org members can read their own org's rows.
-- Writes are reserved to the Supabase service role — used exclusively by the
-- VoltFlow backend (Stripe webhooks, usage recording). No insert/update/delete
-- policy is defined for authenticated users, so PostgREST denies those by default.
alter table public.subscriptions enable row level security;
alter table public.billing_lines enable row level security;

create policy subscriptions_select_own
  on public.subscriptions for select
  using (org_id in (select public.user_org_ids()));

create policy billing_lines_select_own
  on public.billing_lines for select
  using (org_id in (select public.user_org_ids()));
