-- 004_grading_portfolio_runs.sql
-- Backs the Vault, Comic detail and Insights screens:
--   * richer comic metadata (year, key note)
--   * explainable grade reports (range, confidence, per-area scores)
--   * daily portfolio value snapshots for the value-over-time chart
--   * a series/issue catalog so the app can show run gaps

-- ---------------------------------------------------------------- comics
alter table public.comics
  add column if not exists year int,
  add column if not exists key_note text,
  add column if not exists series_id uuid;

-- --------------------------------------------------------- grade reports
-- One current report per comic (the latest scan replaces the previous one).
create table if not exists public.grade_reports (
  comic_id uuid primary key references public.comics(id) on delete cascade,
  grade numeric(3,1) not null check (grade between 0.5 and 10),
  grade_low numeric(3,1) not null check (grade_low between 0.5 and 10),
  grade_high numeric(3,1) not null check (grade_high between 0.5 and 10),
  confidence numeric(3,2) not null check (confidence between 0 and 1),
  -- [{"area": "Corners", "score": 9.4, "note": "..."}]
  defects jsonb not null default '[]'::jsonb,
  exterior_only boolean not null default true,
  -- Which pipeline produced it: 'claude:<model>', 'openai:<model>', 'mock', 'estimate'
  source text not null default 'estimate',
  photos_used int not null default 1,
  created_at timestamptz not null default now(),
  check (grade_low <= grade and grade <= grade_high)
);

alter table public.grade_reports enable row level security;

create policy "grade_reports_select_via_comic"
  on public.grade_reports for select
  using (exists (select 1 from public.comics c where c.id = comic_id and c.user_id = auth.uid()));

-- --------------------------------------------------- portfolio snapshots
-- One row per user per day per lens; written by POST /portfolio/snapshot
-- (run it nightly from a cron job or Supabase scheduled function).
create table if not exists public.portfolio_snapshots (
  user_id uuid not null references public.profiles(id) on delete cascade,
  snapshot_date date not null default current_date,
  lens text not null check (lens in ('all', 'raw', 'certified')),
  total_value numeric(12,2) not null check (total_value >= 0),
  book_count int not null check (book_count >= 0),
  created_at timestamptz not null default now(),
  primary key (user_id, snapshot_date, lens)
);

alter table public.portfolio_snapshots enable row level security;

create policy "portfolio_snapshots_select_own"
  on public.portfolio_snapshots for select using (user_id = auth.uid());

-- -------------------------------------------------------- series catalog
-- Shared reference data (not per user). Load from a catalog source such as
-- Comic Vine or Metron, or from backend/scripts/seed_demo.py for testing.
create table if not exists public.series (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  publisher text not null,
  -- The title string comics are stored under, used to match owned books.
  match_title text not null,
  first_issue int not null default 1,
  last_issue int not null,
  created_at timestamptz not null default now(),
  check (last_issue >= first_issue),
  unique (match_title, first_issue, last_issue)
);

create table if not exists public.series_issues (
  series_id uuid not null references public.series(id) on delete cascade,
  issue_number text not null,
  key_note text,
  raw_price numeric(10,2),
  slab_price numeric(10,2),
  primary key (series_id, issue_number)
);

alter table public.series enable row level security;
alter table public.series_issues enable row level security;

create policy "series_read_all" on public.series for select using (true);
create policy "series_issues_read_all" on public.series_issues for select using (true);

alter table public.comics
  drop constraint if exists comics_series_id_fkey,
  add constraint comics_series_id_fkey
    foreign key (series_id) references public.series(id) on delete set null;
