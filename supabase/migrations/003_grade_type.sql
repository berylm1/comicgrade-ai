-- 003_grade_type.sql
-- Raw vs professionally-slabbed separation (competitive insight: apps that lump
-- raw and certified values together skew portfolio valuations).

alter table public.comics
  add column if not exists grade_type text not null default 'raw'
    check (grade_type in ('raw', 'cgc', 'cbcs', 'pgx', 'other')),
  add column if not exists slab_cert_number text;

-- Existing rows are raw estimates by definition.
update public.comics set grade_type = 'raw' where grade_type is null;

create index if not exists comics_grade_type_idx on public.comics (grade_type);