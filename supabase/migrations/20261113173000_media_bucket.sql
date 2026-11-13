-- Public bucket the platforms fetch images and video from. Only the service role writes to it.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('media', 'media', true, 104857600, array['image/png', 'image/jpeg', 'video/mp4'])
on conflict (id) do nothing;
