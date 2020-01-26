pghops is a command line PostgreSQL schema migration utility written
in Python. It aims to be the simplest database migration utility for
PostgreSQL.

1. [Features](#features)
2. [Demo](#demo)
3. [Usage Overview](#usage-overview)
4. [Installation](#installation)
5. [Best Practices](#best-practices)
6. [Options](#options)
7. [Managing Indexes](#managing-indexes)
8. [Unit Testing](#unit-testing)
9. [FAQ](#faq)
10. [Miscellaneous](#miscellaneous)
11. [License](#license)

## Features

* **Simple version file syntax:** pghops version files are yaml files
  with keys representing directories and values of one or more sql
  file names.
* **Executes scripts with psql:** pghops uses psql to execute all sql,
  leveraging the extensive functionality of the PostgreSQL client. Use
  any psql command in your scripts.
* **Unit testing framework:** pghops comes equipped with its own unit
  testing framework. No more excuses for skipping sql unit tests!
* **All or nothing migrations:** Wrap your entire migration in a
  single transaction or each migration script in its own transaction.
* **All sql commands saved to version table** pghops saves all sql
  executed during migrations to its version table. Make the auditors
  happy!

## Demo

The below terminal session shows how to create a database named `mydb`
that contains two tables: `account` and `account_email`. We will
create a simple test to ensure you cannot insert null emails into the
`account_email` table. Then we will create a database function for
creating accounts, along with another unit test.

```
[mycluster]$ # Create a directory named after the database, along with a script to create the database.
[mycluster]$ mkdir mydb
[mycluster]$ echo "create database mydb;" > mydb/create_database.sql
[mycluster]$ # Create a directory to hold our table definitions.
[mycluster]$ mkdir -p mydb/schemas/public/tables
[mycluster]$ # Create SQL files containing our table definitions.
[mycluster]$ cat - > mydb/schemas/public/tables/account.sql <<EOF
> create table if not exists public.account (
>   account_id bigserial primary key
> );
> EOF
[mycluster]$ cat - > mydb/schemas/public/tables/account_email.sql <<EOF
> create table if not exists public.account_email (
>   account_email_id bigserial primary key
>   , account_id bigint not null references account
>   , email text not null
> );
> EOF
[mycluster]$ # Create our first migration file
[mycluster]$ mkdir mydb/versions
[mycluster]$ cat - > mydb/versions/0001.0001.0001.init.yml <<EOF
> public/tables:
>   - account
>   - account_email
> EOF
[mycluster]$ # Create our first unit test to ensure we cannot insert NULLs into account_email.email
[mycluster]$ mkdir mydb/tests
[mycluster]$ cat - > mydb/tests/01_account_email_test.sql <<EOF
> insert into account values (default);
> insert into account_email (account_id, email) values ((select max(account_id) from account), null);
> EOF
[mycluster]$ # Generated the 'expected' file and review it.
[mycluster]$ pghops_test generate
2019-02-23 14:18:42.452426: Looping through tests in /tmp/mycluster/mydb/tests
2019-02-23 14:18:42.458661: Stopping Postgres pghops-postgresql.
2019-02-23 14:18:42.476721: Starting Postgres pghops-postgresql postgres.
2019-02-23 14:18:45.632209: Done starting postgres pghops-postgresql.
2019-02-23 14:18:45.673046: Migrating cluster /tmp/mycluster.
2019-02-23 14:18:45.673440: Migrating database mydb
2019-02-23 14:18:45.674398: Database mydb does not exist. Creating it with /tmp/mycluster/mydb/create_database.sql.
create database mydb;
CREATE DATABASE

...
<output elided>
...

2019-02-23 14:18:46.106990: Done migrating database mydb
2019-02-23 14:18:46.107123: Done all migrations.
2019-02-23 14:18:46.132066: Generated 01_account_email_test.sql expected file.
2019-02-23 14:18:46.132145: Stopping Postgres pghops-postgresql.
2019-02-23 14:18:48.449079: Done generating expected files!
[mycluster]$ # Review the expected file.
[mycluster]$ cat mydb/tests/01_account_email_expected.txt
insert into account values (default);
INSERT 0 1
insert into account_email (account_id, email) values ((select max(account_id) from account), null);
ERROR:  null value in column "email" violates not-null constraint
DETAIL:  Failing row contains (1, 1, null).
[mycluster]$ # Looks good! We received the error as expected. As a sanity check, run the tests and they should succeeded
[mycluster]$ pghops_test run

...
<output elided>
...

2019-02-23 14:22:31.269604: All tests passed!
[mycluster]$ # Lets run our first migration against a real db!
[mycluster]$ pghops
2019-02-23 14:23:47.225273: Migrating cluster /tmp/mycluster.
2019-02-23 14:23:47.225539: Migrating database mydb
2019-02-23 14:23:47.226114: Database mydb does not exist. Creating it with /tmp/mycluster/mydb/create_database.sql.
CREATE DATABASE


BEGIN
CREATE SCHEMA
CREATE TABLE
CREATE TABLE
CREATE INDEX
INSERT 0 1
CREATE TABLE
CREATE TABLE
INSERT 0 1
COMMIT


2019-02-23 14:23:47.827395: Done migrating database mydb
2019-02-23 14:23:47.827536: Done all migrations.
[mycluster]$ # Check the version table if you wish
[mycluster]$ psql --dbname=mydb --command="select major, minor, patch, label, file_name from pghops.version;"
 major | minor | patch |    label    |            file_name
-------+-------+-------+-------------+---------------------------------
 0000  | 0000  | 0000  | pghops-init | 0000.0000.0000.pghops-init.yaml
 0001  | 0001  | 0001  | init        | 0001.0001.0001.init.yml
(2 rows)

[mycluster]$ # Create a function that creates accounts.
[mycluster]$ mkdir mydb/schemas/public/functions
[mycluster]$ cat - > mydb/schemas/public/functions/create_account.sql <<EOF
create or replace function public.create_account
> (
>   p_email text
> )
> returns bigint
> language plpgsql
> as \$\$
> declare l_account_id bigint;
> begin
>
>   insert into account (account_id) values (default) returning account_id into l_account_id;
>
>   insert into account_email (account_id, email) values (l_account_id, p_email);
>
>   return l_account_id;
>
> end\$\$;
> EOF
[mycluster]$ # Next create our second migration file.
[mycluster]$ cat - > mydb/versions/0001.0002.0001.create_account.yml <<EOF
> public/functions: create_account
> EOF
[mycluster]$ # Create our second test
[mycluster]$ echo "select create_account('x@example.com');" > mydb/tests/02_create_account_test.sql
[mycluster]$ pghops_test generate
2019-02-23 14:35:44.742060: Looping through tests in /tmp/mycluster/mydb/tests
2019-02-23 14:35:44.748353: Stopping Postgres pghops-postgresql.
2019-02-23 14:35:44.764216: Starting Postgres pghops-postgresql postgres.
2019-02-23 14:35:47.726734: Done starting postgres pghops-postgresql.
2019-02-23 14:35:47.767687: Migrating cluster /tmp/mycluster.
2019-02-23 14:35:47.768116: Migrating database mydb
2019-02-23 14:35:47.769223: Database mydb does not exist. Creating it with /tmp/mycluster/mydb/create_database.sql.
...
<output elided>
...

2019-02-23 14:35:48.230893: Done migrating database mydb
2019-02-23 14:35:48.230981: Done all migrations.
2019-02-23 14:35:48.251236: Generated 01_account_email_test.sql expected file.
2019-02-23 14:35:48.269521: Generated 02_create_account_test.sql expected file.
2019-02-23 14:35:48.269596: Stopping Postgres pghops-postgresql.
2019-02-23 14:35:50.672626: Done generating expected files!
[mycluster]$ cat mydb/tests/02_create_account_expected.txt
select create_account('x@example.com');
 create_account
----------------
              2
(1 row)
[mycluster]$ # Our new db function works! Lets run a migartion to update our db
[mycluster]$ pghops
2019-02-23 14:37:13.523780: Migrating cluster /tmp/mycluster.
2019-02-23 14:37:13.524050: Migrating database mydb
BEGIN
CREATE FUNCTION
INSERT 0 1
COMMIT


2019-02-23 14:37:13.572099: Done migrating database mydb
2019-02-23 14:37:13.572224: Done all migrations.
[mycluster]$ psql --dbname=mydb --command="select major, minor, patch, label, file_name from pghops.version;"
 major | minor | patch |     label      |             file_name
-------+-------+-------+----------------+-----------------------------------
 0000  | 0000  | 0000  | pghops-init    | 0000.0000.0000.pghops-init.yaml
 0001  | 0001  | 0001  | init           | 0001.0001.0001.init.yml
 0001  | 0002  | 0001  | create_account | 0001.0002.0001.create_account.yml
(3 rows)

[mycluster]$


```

## Usage Overview

When you install PostgreSQL you initialize a storage area on disk
called a [database
cluster](https://www.postgresql.org/docs/current/creating-cluster.html),
which is a collection of databases managed by a single instance of
PostgreSQL. pghops expects you to place all files associated to
building and defining your cluster in a single directory, referred to
henceforth as the `cluster_directory`. Each sub-directory in
`cluster_directory` should be the name of a database within your
cluster (if not, you can add a file named `databases` that contains
the list of database directories).

For example, say your `cluster_directory` is /tmp/pghops/main and you
have two databases - dba and dbb. Your directory structure would look
like:
```
└── main
    ├── dba
    └── dbb
```

pghops requires each database directory to have a sub-directory named
`versions` which contain, you guessed it, all of you database
migration files. Each migration file must follow the following
versioning convention:

`<major>.<minor>.<patch>.<label>.yml`

This allows you to follow [Semantic Versioning](https://semver.org/)
if you choose. pghops parses these file names and saves them to the
`pghops.version` table.

If pghops detects the database does not exist on the cluster, pghops
will create it if the database directory has a file named
`create_database.sql` containing the database creation
commands. pghops records all migrations in a table named `version` in
the schema `pghops`. If this table does not exist, pghops will run the
included `0000.0000.0000.pghops-init.yaml` script first to create it.

Each version file must be in yaml format and have a yaml or yml
suffix. The file can only contain comments and key / value pairs, with
keys representing directories and values of either a single file or a
list of files to execute. Directories can be absolute or relative to
either the database directory or a directory named `schemas` within
the database directory. We recommend laying out your directory
structure the same as pgAdmin's. For example, if your
`cluster_directory` looks like:
```
├── cluster_a
│   ├── databases
│   ├── db_a1
│   │   ├── create_database.sql
│   │   ├── schemas
│   │   │   └── public
│   │   │       ├── functions
│   │   │       ├── tables
│   │   │       │   └── visits.sql
│   │   │       └── views
│   │   │           ├── vistor_view.sql
│   │   │           └── location_view.sql
│   │   └── versions
│   │       ├── 0000.0011.0001.change-a.yml
│   │       ├── 0000.0021.0002.change-b.yml
│   │       └── 0000.0032.0000.change-c.yml
│   ├── db_a2
│   │   ├── create_database.sql
│   │   ├── data
│   │   │   └── init-data.sql
│   │   ├── schemas
│   │   │   └── public
│   │   │       ├── functions
│   │   │       ├── tables
│   │   │       │   └── user.sql
│   │   │       └── views
│   │   │           ├── user_view.sql
│   │   │           └── accounts_view.sql
│   │   └── versions
│   │       ├── 0000.0001.0001.feature-a.yml
│   │       ├── 0000.0001.0002.feature-b.yml
│   │       └── 0000.0002.0000.feature-c.yml
```

and you want to use pghops to create new views defined in visitor_view
and location_view, create a new migration script in db_a1/versions
such as `0000.0033.0000.new-views.yml` and add the lines:

```
schemas/public/views:
  - visitor_view.sql
  - location_view.sql
```

You can optionally omit the sql suffix. Again, `schemas` is optional
as well.

Run pghops by cd'ing into cluster_directory and running

```
pghops
```

See below for command line parameters. You can also pass the path of
`cluster_directory` as the first argument.

When you run pghops, it will concatenate the contents of
visitor_view.sql and location_view.sql into a single file and then
execute it via psql in a single transaction. If successful, a new
record is added to pghops.version and your migration is complete! For
more examples see the [test
clusters](src/tests/test_clusters/cluster_a).

## Installation

`pghops` requires python 3.7 and the psql client. `pghops_test`
requires a docker compatible container runtime. Install `pghops` with
pip:

```
pip3 install pghops
```

This should add the executeables `pghops`, `pghops_test`, and
`pghops_create_indexes` to your path.

## Best Practices

### Directory layout for your sql code
I recommend following the same layout as pgAdmin. For example, if you
have a database named dba, one possibility is:
```
├── dba
│   ├── data
│   ├── schemas
│   │   ├── myschema
│   │   │   ├── functions
│   │   │   ├── tables
│   │   │   └── views
│   │   └── public
│   │       ├── functions
│   │       ├── tables
│   │       └── views
│   └── versions
```
The `data` directory can contain scripts to load data during your
migrations.

### Versioning
pghops is liberal when determining which migration files to
execute. It ignores the major, minor, and patch fields in the
pghops.version table and only looks at file_names.

As such, you can use whichever versioning scheme you like. [Semantic
Versioning](https://semver.org/) is definitely a solid option. Another
scheme, which requires slightly more effort for tracking but works
well when dealing with multiple people working with many branches, is
to use an auto-incrementing number for `major` that increases on every
merge into your master/production branch. For `minor`, use something
that refers to either a feature branch or something that links back to
a ticketing system. For `patch`, use an incrementing number for
each migration file you create for the feature. Use `label` to
differentiate between two people creating migration scripts for the
same feature at the same time. This also helps to prevent merge
conflicts.

### Idempotency
Essentially this means if you execute the same sql twice all changes
will only take affect once. So use "if not exists" when writing DDL
statements and check for the presence of your records first when
executing update statements (or use the `on conflict do nothing`
clause).

### Keep old migration files up to date
The pghops.version table and Git (or another VCS) should be all you
need for auditing and history purposes. If you make changes that would
break older migration scripts when run on a new database, best to go
back and update the older scripts. Then you can use pghops to create a
new database from scratch for failover, setting up new environments,
or testing purposes.

### Passwords and psql

Normally you want to avoid having to enter your password for every
psql call. A couple options:

1. Setup the user that runs pghops with password-less authentication,
   such as [trust or
   peer](https://www.postgresql.org/docs/current/auth-pg-hba-conf.html). Best
   then to run pghops on the same box as PostgreSQL.
2. Use a [password
   file](https://www.postgresql.org/docs/current/libpq-pgpass.html).

## Options

pghops has many configuration options, which you can set via the
command line, environment variables or various property files. Options
are loaded in the following order, from highest to lowest priority:

1. Command line arguments
2. Properties in the file specified by the `--options-file` command line
   argument.
3. Environment variables.
4. Properties in `<cluster-dir>/<db>/pghops.properties`
5. Properties in `<cluster-dir>/pghops.properties`
6. Properties in `pghops/conf/default.properties`

Property files should be in yaml format and contain key/value pairs.

pghops treats options in property files that only differ in case or
usage of underscore versus hyphen the same. For example:

```
wrap-all-in-transaction
wrap_all_in_transaction
Wrap_All_In_Transaction
```

all refer to the same option. Environment variables should use
underscores instead of hyphens, be in all caps, and have a prefix of
PGHOPS_. For example, the environment varaible for the
wrap-all-in-transaction property above is
PGHOPS_WRAP_ALL_IN_TRANSACTION.

psql's environment variables are also in effect.

pghops options are as follows:

**cluster_directory** - The first argument to pghops. Defaults to the
current working directory. The base directory containing your database
sql.

**dbname** - By default pghops will migrate all dbs in the cluster
directory. Use this option to only update the specified db.

**cluster_map** - Path to a yaml file containing a map of cluster names to
directories. The cluster name can then be supplied as the
cluster_directory argument instead of a directory.

**dry_run** - Do not execute the migration, only print the files that
would have executed.

**verbosity** - Verbosity level. One of default, verbose, or terse.
"terse" only prints errors. "verbose" echos all executed sql.

**psql_base_args** - "Base" arguments to psql. Defaults to "--set
ON_ERROR_STOP=1 --no-psqlrc". Use this in combination with
psql_arguments.

**psql_arguments** - A list of arguments to provide to psql, such as
--host, --port, etc.

**db_conninfo** - Alternative way to specify the connection parameters to
psql.

**wrap_all_in_transaction** - When true, the default, pghops will wrap the
entire migration in a single transaction.

**wrap_each_version_in_transaction** - When true, each version script will
run in its own transaction, not the entire migration.

**fail_if_unable_to_connect** - When true, the default, pghops will raise
an error if it cannot connect to the database server.

**fail_if_standby** - When true, the default, pghops will raise an error
if it can connect to the database server but the database server is in
standby mode.

**save_sql_to_version_table** - When true, the default, pghops will save
all executed sql to the pghops.version table. Consider setting to
false for large migrations or migrations that contain sensitive info.

**save_indexes** - When true, the default, pghops scans you sql code for
create index statements and saves them to the pghops.index table. See
below for more details.

**migration_file** - Use this option to only execute the supplied file
instead of all files in the versions directory.

**script_suffixes** - A case-insensitive comma separated list of
suffixes that migration file names must match in order to be
executed. Defaults to yml and yaml.

**option_file** - When supplied, also load options contained within
this properties file.

## Managing Indexes

As your schema evolves, you may find the need to create new indexes on
large, existing tables. If creating indexes during the migration is
unacceptable, you can have pghops manage indexes for you so you can
create them asynchronously at a later time.

By setting the option `save-indexes` to true (the default), pghops
will scan your sql code for create index statements and save any to
`pghops.index`. For pghops to track an index, ensure the following:

1. The index statement resides in a file with a '.sql' suffix.
2. The entire index statement resides on a single line.
3. The index statement begins on the first column of the line. pghops
   ignores any indexes statements preceded by white space. Useful if,
   for example, you have a function that creates a temp table and
   defines indexes on said temp table, you do not want pghops to
   manage this index.
4. Use fully qualified table names in you index definitions
   (schema.table_name). The create indexes script first checks for the
   existence of the table before executing the index statement, and
   when pghops saves an index it does not analyze any preceding set
   path statements. If you do not use a fully qualified table name
   pghops will not save the index.
5. The statement uses `if not exists` so it can be run multiple times
   without causing an error.
6. The scanning for indexes is not perfect. If you use unconventional
   names for your index or table which requires quoting the name,
   pghops cannot parse the statement correctly.

By scanning your code for indexes, you can define indexes in the same
files as their table and pghops will add them to pghops.index
automatically during the next migration.

For every record in `pghops.index`, `pghops_create_indexes` will first
check to see if the table_name is a valid table. It then checks the
`enabled` flag and, if set, executes the sql in `definition`. The
script runs in parallel based on the number of cpu cores, although
this advantage is mitigated in more recent PostgreSQLs that can create
a single index in parallel automatically.

## Unit Testing

Using the `pghops_test` command, you can create and run simple SQL
unit tests. You will need a docker compatible container runtime
installed as the tests are run in a PostgreSQL container. Here's how
it works:

1. Create a directory named `tests` within your database directory.
2. In the `tests` directory, create sql files ending in
   `_test.sql`. Usually you will want the file names to contain a
   number for ordering purposes, such as `01_base_test.sql`.
3. Run `pghops_test generate`. This will launch a PostgreSQL
   container, run the migration, then generate companion files for
   each sql test file. For example, for the test file
   `01_base_test.sql` it will generate `01_base_expected.txt`.
4. Review the generated expected file. Ensure there is no host or
   environment specific output, such as host names or timestamps.
5. As your schema evolves, you can run `pghops_test run` to run your
   unit test. It will launch a new PostgreSQL container, run the
   migration, execute the unit test sql files and compare the output
   to the contents of the expected files.

If you create many tests, you can organize them into suites by create
sub-directories within the `tests` directory. Each suite is run within
its own container.

### Test Options

Options for `pghops_test` are loaded in the same way as `pghops`
except it looks for property files named `pghops-test.properties` in
the test and test-suite directories. Test specific properties only
apply when running the tests, not when running the initial migration
in the container.

**command** - The only required option. Either `run` or `generate`.

**test** - When provided, only runs the specific test. You can specify
a suite name, specific file, or specific file within a suite such as
my-suite/my-file_test.sql.

**container_name** - The name of the image to use. Defaults to
postgresql.

**container_tag** - Optional tag. If omitted, uses latest.

**container_name** - The name of the container to create. Defaults to
pghops-postgresql.

**container_runtime** - Defaults to docker. Also tested with podman.

**skip_container_shutdown** - Do not kill the container after running
the tests.

**ignore_whitespace** - Whether or not to ignore whitespace when
comparing output against the expected files.

**psql_base_migrations_args** - Similar to psql_base_args but only
applies when running the migration.

`pghops_test` also accepts the following arguments that are identical
to the `pghops` arguments:

**cluster_directory**, **dbname**, **psql_base_args**,
**psql_arguments**, **db_conninfo**, **verbosity**, **option_file**

## FAQ

### What does pghops stand for?

Either PostGresql Highly OPinionated migrationS. Or maybe you can use
pghops to "hop" to your next database version. Take your pick.

### Why make pghops PostgresSQL specific? Why not make it database agnosistic by using drivers for the Python Database API?

By using psql you can leverage all of its power - your sql can contain
any psql meta command which is not possible to do with adapters such
as Psycopg.

### Is there support for rolling back migrations?

No built in support. In a perfect world each database migration script
would be accompanied by a rollback script. But if something goes wrong
on production and you need to roll back, do you really feel
comfortable executing the rollback script? Have you tested all
possible state that the rollback script can encounter?

In my experience the need to roll back is infrequent and when it is
necessary, careful examination of the database must happen before any
changes can take place. However, if you insist on having rollback
scripts, you can initially create rollback files in the same versions
directory and name them with a non-yaml suffix, such as
.rollback. Then when you need to rollback, run pghops with the
`--migration-file` option to run the rollback script. If you wish to
erase the records from the pghops.version table, you will have to do
that manually.

### I have dependencies between my databases and I need pghops to execute migrations in a particular order.

In your `cluster_directory`, create a file named `databases` and list
the databases in the required order.

### What happens if I need to execute sql that cannot be in a transaction?

Probably best to include a `commit` statement immediately preceding
the sql that cannot run inside a transaction, followed by a `begin`
statement to start a new transaction. You could also omit transactions
for this pghops run by setting the options wrap-all-in-transaction and
wrap-each-version-in-transaction to false.

### When working on a unit test, I don't want to re-run the entire migration when checking my changes.

Set skip_container_shutdown to True and supply a test name in your command. Example:

`pghops_test --skip-container-shutdown t generate 01_base_test.sql`

Then next time you re-run the above command it will immediately
execute 01_base_test.sql against the container without having to
re-launch.

## Miscellaneous

pghops was developed and tested on GNU/Linux. Feel free to report bugs
and contribute patches.

## License

GPLv3. See [COPYING](COPYING).
