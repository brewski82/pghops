create table if not exists pghops.index (
  index_id bigserial primary key
  , table_name text not null
  , definition text not null
  , enabled boolean not null default true
  , executed_time timestamp with time zone not null default current_timestamp
  , notes text
);

create unique index pghops_index_unique_index on pghops.index(regexp_replace(definition, '\s', ''));
