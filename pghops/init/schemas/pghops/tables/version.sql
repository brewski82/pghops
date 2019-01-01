create table if not exists pghops.version (
  version_id bigserial primary key
  , major text not null
  , minor text not null
  , patch text not null
  , label text
  , file_name text not null unique
  , file_md5 text not null
  , migration_sql text
  , user_name text not null default session_user
  , user_ip inet default inet_client_addr()
  , executed_time timestamp with time zone not null default current_timestamp
  , notes text
);
