create schema if not exists pghops;
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
create table if not exists pghops.index (
  index_id bigserial primary key
  , table_name text not null
  , definition text not null
  , enabled boolean not null default true
  , executed_time timestamp with time zone not null default current_timestamp
  , notes text
);

create unique index pghops_index_unique_index on pghops.index(regexp_replace(definition, '\s', ''));
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
  , '0000'
  , '0000'
  , 'pghops-init'
  , '0000.0000.0000.pghops-init.yaml'
  , 'ab80eb0560996a6f13b71ce57143ea10'
  , 'create schema if not exists pghops;
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
create table if not exists pghops.index (
  index_id bigserial primary key
  , table_name text not null
  , definition text not null
  , enabled boolean not null default true
  , executed_time timestamp with time zone not null default current_timestamp
  , notes text
);

create unique index pghops_index_unique_index on pghops.index(regexp_replace(definition, ''\s'', ''''));
'
);
