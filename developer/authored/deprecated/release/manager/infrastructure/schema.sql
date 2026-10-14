-- schema.sql
--
-- 5.6.1 read and executed by db.ensure_schema



CREATE TABLE subu (
  id            INTEGER PRIMARY KEY,
  owner         TEXT NOT NULL,           -- root user, e.g. 'Thomas'
  name          TEXT NOT NULL,           -- leaf, e.g. 'US', 'Rabbit'
  full_unix_name TEXT NOT NULL UNIQUE,   -- e.g. 'Thomas_US_Rabbit'
  path          TEXT NOT NULL,           -- e.g. 'Thomas US Rabbit'
  netns_name    TEXT NOT NULL,
  wg_id         INTEGER,                 -- nullable for now
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
