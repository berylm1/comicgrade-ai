-- 006_nightly_snapshots.sql
-- Records every collection's value once a night inside Supabase (pg_cron), so
-- the Vault chart fills with real history without an external cron job.
-- Same totals as POST /portfolio/snapshot: per user, for each lens
--   all       = every book
--   raw       = grade_type 'raw' (or unset)
--   certified = every other grade_type (cgc, cbcs, pgx, other)
-- Safe to re-run: it replaces the function and the schedule.

create or replace function public.take_portfolio_snapshots(on_date date default current_date)
returns integer
language sql
security definer
set search_path = public
as $$
  with books as (
    select user_id,
           coalesce(current_market_value, 0) as value,
           coalesce(grade_type, 'raw') = 'raw' as is_raw
      from public.comics
     where user_id is not null
  ),
  totals as (
    select user_id, 'all'::text as lens, sum(value) as total_value, count(*) as book_count
      from books group by user_id
    union all
    select user_id, 'raw', coalesce(sum(value) filter (where is_raw), 0), count(*) filter (where is_raw)
      from books group by user_id
    union all
    select user_id, 'certified', coalesce(sum(value) filter (where not is_raw), 0), count(*) filter (where not is_raw)
      from books group by user_id
  ),
  written as (
    insert into public.portfolio_snapshots (user_id, snapshot_date, lens, total_value, book_count)
    select user_id, on_date, lens, round(total_value, 2), book_count from totals
    on conflict (user_id, snapshot_date, lens) do update
      set total_value = excluded.total_value,
          book_count = excluded.book_count,
          created_at = now()
    returning 1
  )
  select count(*)::integer from written;
$$;

-- Only the server may run it: PostgREST exposes public functions as RPCs, so
-- take it away from the public, anon and signed-in roles.
revoke all on function public.take_portfolio_snapshots(date) from public, anon, authenticated;
grant execute on function public.take_portfolio_snapshots(date) to service_role;

-- ---------------------------------------------------------------- schedule
-- Every night at 06:17 UTC (about 1 a.m. US Eastern). Change the cron
-- expression to move it. Scheduling under the same name replaces the job.
create extension if not exists pg_cron with schema extensions;

select cron.schedule(
  'comicgrade-nightly-snapshots',
  '17 6 * * *',
  $$select public.take_portfolio_snapshots()$$
);

-- To check:  select * from cron.job where jobname = 'comicgrade-nightly-snapshots';
-- Last runs: select * from cron.job_run_details order by start_time desc limit 5;
-- To stop:   select cron.unschedule('comicgrade-nightly-snapshots');
