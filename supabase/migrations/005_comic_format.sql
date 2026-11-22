-- 005_comic_format.sql
-- Annuals and collected editions reuse issue numbers (Amazing Spider-Man Annual #2
-- is not Amazing Spider-Man #2; the Detective Comics #1000 Deluxe Edition is not
-- the single issue), so the book's format is part of its identity.

alter table public.comics
  add column if not exists format text not null default 'single_issue'
    check (format in ('single_issue', 'annual', 'collected_edition', 'other'));
