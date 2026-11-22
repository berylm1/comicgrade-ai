-- 002_storage_bucket.sql
-- Cover-image storage bucket + access policies.

insert into storage.buckets (id, name, public)
values ('cover-images', 'cover-images', true)
on conflict (id) do nothing;

create policy "cover_images_select_public"
  on storage.objects for select
  using (bucket_id = 'cover-images');

create policy "cover_images_insert_authenticated"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'cover-images');

create policy "cover_images_update_owner"
  on storage.objects for update to authenticated
  using (bucket_id = 'cover-images');

create policy "cover_images_delete_owner"
  on storage.objects for delete to authenticated
  using (bucket_id = 'cover-images');