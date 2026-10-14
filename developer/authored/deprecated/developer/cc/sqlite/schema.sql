-- Schema for the subu server
--

-- List Tables
-- SQLite does not support PSQL style types
--
--  CREATE TYPE List AS (
--    id SERIAL,          -- Integer ID
--    name TEXT NOT NULL  -- Name of the list entry
--  );
--
-- so though these all have the same `List` form, they are declared independently
--
  CREATE TABLE db_property_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
  );

  CREATE TABLE db_event_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
  );

  CREATE TABLE shell_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
  );

  CREATE TABLE system_resource_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
  );

  CREATE TABLE user_type_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
  );

-- Data Tables
--
  CREATE TABLE db_property (
    id INTEGER PRIMARY KEY,
    property_id INTEGER NOT NULL REFERENCES db_property_list(id),
    type TEXT NOT NULL,
    value TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE db_event (
    id INTEGER PRIMARY KEY,
    event_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_id INTEGER NOT NULL REFERENCES db_event_list(id),
    user_id INTEGER REFERENCES user(id)
  );

  CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    login_gid INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    home_directory TEXT NOT NULL,
    shell INTEGER NOT NULL REFERENCES shell_list(id),
    parent_id INTEGER REFERENCES user(id),
    user_type_id INTEGER NOT NULL REFERENCES user_type_list(id),
    status TEXT DEFAULT 'active'
  );

  CREATE TABLE share (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id),
    other_user_id INTEGER NOT NULL REFERENCES user(id),
    permissions TEXT NOT NULL
  );

  CREATE TABLE system_resource (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id),
    resource_id INTEGER NOT NULL REFERENCES system_resource_list(id),
    granted_by INTEGER REFERENCES user(id)
  );
