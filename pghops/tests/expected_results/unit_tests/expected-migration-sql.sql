insert into pghops.version
(
  major
  , minor
  , patch
  , label
  , file_name
  , file_md5
  , migration_sql
) values
(
  '0000'
  , '0001'
  , '0000'
  , 'init'
  , '0000.0001.0000.init.yml'
  , '87cc9caf86ad72853163d145567cdad3'
  , 'create table public.user (
  user_id serial primary key
  , user_name text
);

create index if not exists public_user_user_name_index on public.user(user_name);
create or replace view public.user_view as
select * from public.user;
select 1;
select 2;
select ''hi'' as x;
'
);
