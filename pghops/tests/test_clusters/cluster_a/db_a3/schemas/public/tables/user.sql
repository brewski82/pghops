create table public.user (
  user_id serial primary key
  , user_name text
);

create index if not exists public_user_user_name_index on public.user(user_name);
