-- schema_system.sql
--
-- The system database, standard 5.0, at /var/lib/SubU/system.sqlite3. It is
-- the system's own record, and the authority for which users of storage
-- databases have accounts on this system. It is kept under /var, which holds
-- state, not under /etc, which holds configuration: a system whose root file
-- system is rolled back from a snapshot keeps /var as it was, so the record
-- of the system uids already given out is not rolled back with /etc/passwd.
--
--   system uuid     names this system
--   system uid      an account's uid on this system, in /etc/passwd
--   database uuid   names a storage database
--   database uid    a user's uid in that storage database's own numbering
-- Times are for people to read; the series number in identity is authoritative.

-- This system: its system uuid and the head of its hash chain. One row.
CREATE TABLE identity (
  system_uuid  TEXT NOT NULL,
  series       INTEGER NOT NULL,
  head_hash    TEXT NOT NULL,
  created      TEXT NOT NULL
);

-- The SubU standards this database follows.
CREATE TABLE standard (
  version  TEXT PRIMARY KEY
);

-- The range of system uids SubU gives out when it makes an account. One row.
CREATE TABLE system_uid_range (
  first  INTEGER NOT NULL,
  last   INTEGER NOT NULL
);

-- The system map: each account that is the same user as a user of a storage
-- database. A row is never deleted; when the two stop being the same user it
-- is retired. A system uid that appears in any row, in use or retired, is
-- never given to an account SubU makes. An account adopted by SubU, one that
-- existed before, may be mapped again after its row is retired.
CREATE TABLE system_map (
  id             INTEGER PRIMARY KEY,
  system_uid     INTEGER NOT NULL,
  system_gid     INTEGER NOT NULL,
  account_name   TEXT NOT NULL,         -- kept so that an account lost from /etc/passwd can be made again
  database_uuid  TEXT NOT NULL,
  database_uid   INTEGER NOT NULL,
  account        TEXT NOT NULL CHECK (account IN ('made' ,'adopted')),
  state          TEXT NOT NULL CHECK (state IN ('in use' ,'retired')),
  mapped         TEXT NOT NULL,
  retired        TEXT
);
CREATE UNIQUE INDEX system_map_system_uid_in_use ON system_map(system_uid) WHERE state = 'in use';
CREATE UNIQUE INDEX system_map_database_user_in_use ON system_map(database_uuid ,database_uid) WHERE state = 'in use';

-- How many SubUs each account may have below it. An account with no row may
-- have none.
CREATE TABLE user_limit (
  system_uid  INTEGER PRIMARY KEY,
  maximum     INTEGER NOT NULL
);

-- Every change. hash covers previous_hash, series, description, change and nonce.
CREATE TABLE transaction_log (
  series         INTEGER PRIMARY KEY,
  previous_hash  TEXT NOT NULL,
  nonce          TEXT NOT NULL,
  description    TEXT NOT NULL,
  change         TEXT NOT NULL,
  hash           TEXT NOT NULL,
  time           TEXT NOT NULL
);
