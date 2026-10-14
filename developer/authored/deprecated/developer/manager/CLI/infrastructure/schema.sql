-- schema.sql
--
-- Schema for subu manager, including device-aware subu tracking.

-- Devices that can hold one or more masu homes.
-- Each row represents a physical (or logical) storage volume
-- identified by a mapname like 'Eagle' and optionally by UUIDs.
CREATE TABLE device (
  id           INTEGER PRIMARY KEY,
  mapname      TEXT NOT NULL UNIQUE,   -- e.g. 'Eagle'
  fs_uuid      TEXT,                   -- filesystem UUID (optional)
  luks_uuid    TEXT,                   -- LUKS UUID (optional)
  mount_point  TEXT NOT NULL,          -- e.g. '/mnt/Eagle'
  kind         TEXT NOT NULL DEFAULT 'external', -- 'local','external','encrypted',...
  state        TEXT NOT NULL DEFAULT 'offline',  -- 'online','offline','error'
  last_seen    TEXT NOT NULL           -- ISO8601 UTC timestamp
);

-- parents via parent_id; one row per node in the tree
CREATE TABLE subu_node (
  id             INTEGER PRIMARY KEY,
  owner          TEXT NOT NULL,            -- masu
  name           TEXT NOT NULL,            -- this segment (e.g., developer, bolt)
  parent_id      INTEGER,                  -- NULL for top-level subu under owner
  full_unix_name TEXT NOT NULL UNIQUE,     -- e.g., Thomas_developer_bolt
  full_path      TEXT NOT NULL,            -- e.g., "Thomas developer bolt"
  netns_name     TEXT NOT NULL,            -- default = full_unix_name
  device_id      INTEGER,                  -- NULL=local
  is_online      INTEGER NOT NULL DEFAULT 1,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  FOREIGN KEY(parent_id) REFERENCES subu_node(id),
  FOREIGN KEY(device_id) REFERENCES device(id),
  UNIQUE(owner, name, parent_id)           -- no duplicate siblings
);

CREATE INDEX idx_node_owner_parent   ON subu_node(owner, parent_id);
CREATE INDEX idx_node_device         ON subu_node(device_id);

