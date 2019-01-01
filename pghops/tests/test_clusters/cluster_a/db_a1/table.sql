create table testing(
 x int
);

create index if not exists test_index_1 on testing(x);

create unique index test_index_2 on testing(x);

create UNIQUE index if not exists test_index_3 on testing(x);

create UNIQUE index if not exists test_index_4 on customschema.testing(x);

-- Do not save this index since it is indented.
 create UNIQUE index test_index_5 on customschema.testing(x);

-- Omit this index since it is on multiple lines.
create UNIQUE index test_index_6 on
customschema.testing(x);
