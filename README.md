pghops is a command line PostgreSQL schema migration utility written
in Python.

## Features

* **Simple version file syntax:** pghops version files are yaml files
  with keys representing directories and values of one or more sql
  file names.
* **Executes scripts with psql:** pghops uses psql to execute all sql,
  leveraging the extensive functionality of the PostgreSQL client. Use
  any psql command.
* **All or nothing migrations:** Wrap your entire migration in a
  single transaction or each migration script in a transaction if you
  prefer.
* **All sql commands saved to version table** pghops saves all sql
  executed during migrations to it version table.

## Usage Overview

When you install PostgreSQL you initialize a storage area on disk
called a [database
cluster](https://www.postgresql.org/docs/current/creating-cluster.html),
which is a collection of databases managed by a single instance of
PostgreSQL. pghops expects you to place all files associated to
building and defining your cluster in a single directory, referred to
henceforth as the `cluster_directory`. Each sub-directory in
`cluster_directory` should be the name of a database within your
cluster (if not, you can add a file named `databases` to list the
database directories).

For example, say your `cluster_directory` is /tmp/pghops/main and you
have two databases - dba and dbb. Your directory structure would look
like:
```
└── main
    ├── dba
    └── dbb
```

pghops requires each database directory to have a directory named
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
the schema `pghops`. If this table does not exists pghops will run the
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
such as `0000.0033.0000.new-views.yml` and add lines such as:

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
cluster_directory as the first argument.

When you run pghops, it will concatenate the contents of
visitor_view.sql and location_view.sql into a single file and then
execute it via psql in a single transaction. If successful, a new
record is added to pghops.version and your migration is complete! For
more examples see the [test
clusters](src/tests/test_clusters/cluster_a).

## Installation

pghops requires python 3.7 and the psql client. Install with pip:

```
pip3 install pghops
```

This should add the executeables pghops and create_indexes to your
path.

## Best Practices

### Directory layout for your sql code
We recommend following the same layout as pgAdmin. For example, if you
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
well when dealing with multiple people working with many branches is
to an auto-incrementing number for `major` that increases on every
merge into your master/production branch. For `minor`, use something
that refers to either a feature branch or something that links back to
a ticketing system. For `patch`, use an auto-incrementing number for
each migration file you create for the feature. Use `label` to
differentiate between two people creating migration scripts for the
same feature at the same time. This also helps to prevent merge
conflicts.

### Idempotency
Essentially this means if you execute the same sql twice all changes
will only take affect once. So use "if [not] exists" when write DDL
statements and check for the presence of your records first when
executing update statements (or use the `on conflict do nothing`
clause).

### Keep old migration files up to date
The pghops.version table and Git (or another VCS) should be all you
need for auditing and history purposes. If you make changes that would
break older migration scripts if run on a new database, best to go
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

pghops has many congratulation options, which you can set via the
command line, environment variables or various property files. Options
are loaded in the following order, from highest to lowest priority:

1. Command line arguments
2. Properties in the file specified by the --options-file command line
   argument.
3. Environment variables.
4. Properties in <cluster-dir>/<db>/pghops.properties
5. Properties in <cluster-dir>/pghops.properties
6. Properties in pghops/conf/default.properties

Property files should be in yaml format and contain key/value pairs.

pghops treats options in property files that only differ in case or
usage of underscore versus hyphen the same. For example:

wrap-all-in-transaction
wrap_all_in_transaction
Wrap_All_In_Transaction

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
ON_ERROR_STOP=1". Use this in combination with psql_arguments.

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

For every record in `pghops.index`, `create_indexes` will first check
to see if the table_name is a valid table. It then checks the
`enabled` flag and, if set, executes the sql in `definition`. The
script runs in parallel based on the number of cpu cores, although
this advantage is mitigated in more recent PostgreSQLs that can create
a single index in parallel automatically.

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

In my experience the need to rolling back is infrequent and when it is
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

## Miscellaneous

pghops was developed and tested on a GNU/Linux. Feel free to report
bugs and contribute patches.

## License

GPLv3. See [COPYING](COPYING).
