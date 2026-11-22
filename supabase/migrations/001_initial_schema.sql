-- 001_initial_schema.sql
-- ComicGrade AI — core tables. Run top-to-bottom (or `supabase db push`).

-- profiles: one row per Supabase auth user
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles_select_own"
  on public.profiles for select using (auth.uid() = id);
create policy "profiles_upsert_own"
  on public.profiles for insert with check (auth.uid() = id);
create policy "profiles_update_own"
  on public.profiles for update using (auth.uid() = id);

-- comics: the user's scanned collection
create table if not exists public.comics (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  issue_number text not null,
  publisher text not null default 'Unknown',
  cover_image_url text,
  estimated_grade numeric(3,1),
  current_market_value numeric(10,2),
  user_id uuid references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now()
);

create index if not exists comics_user_id_idx on public.comics (user_id);

alter table public.comics enable row level security;

create policy "comics_select_own"
  on public.comics for select using (user_id = auth.uid());
create policy "comics_insert_own"
  on public.comics for insert with check (user_id = auth.uid());
create policy "comics_update_own"
  on public.comics for update using (user_id = auth.uid());
create policy "comics_delete_own"
  on public.comics for delete using (user_id = auth.uid());

-- price_history: sale/valuation observations per comic
create table if not exists public.price_history (
  id bigint generated always as identity primary key,
  comic_id uuid not null references public.comics(id) on delete cascade,
  sale_date date not null default current_date,
  price numeric(10,2) not null check (price >= 0),
  source text not null default 'manual',
  created_at timestamptz not null default now()
);

create index if not exists price_history_comic_idx on public.price_history (comic_id, sale_date);

alter table public.price_history enable row level security;

create policy "price_history_select_via_comic"
  on public.price_history for select
  using (exists (select 1 from public.comics c where c.id = comic_id and c.user_id = auth.uid()));
create policy "price_history_insert_via_comic"
  on public.price_history for insert
  with check (exists (select 1 from public.comics c where c.id = comic_id and c.user_id = auth.uid()));