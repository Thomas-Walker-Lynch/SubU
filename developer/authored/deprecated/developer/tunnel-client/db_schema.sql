PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA user_version = 300; -- v3.00: singular, capitalized tables; private_key removed

-- meta first (so later INSERTs succeed)
CREATE TABLE IF NOT EXISTS Meta (
  key   TEXT PRIMARY KEY
  ,value TEXT NOT NULL
);
INSERT OR REPLACE INTO Meta(key,value) VALUES ('schema','wg-client-v3.00-Ifaces');
INSERT OR IGNORE  INTO Meta(key,value) VALUES ('subu_cidr','10.0.0.0/24');

-- Iface, interface, device, netdevice, link — table of them
CREATE TABLE IF NOT EXISTS Iface (
  id                 INTEGER PRIMARY KEY
  ,created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
  ,updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
  ,iface              TEXT NOT NULL UNIQUE   -- kernel interface name as shown by ip link (e.g., wg0, x6)
  ,rt_table_id        INTEGER                       -- e.g. 1002, unused
  ,rt_table_name      TEXT                          -- if NULL, default to iface (see view)
  -- legacy caches (kept for compatibility; may be NULL)
  ,bound_user         TEXT
  ,bound_uid          INTEGER
  ,local_address_cidr TEXT                 -- e.g. '10.8.0.2/32'
  -- secrets: private key is NO LONGER stored in DB (lives under key/<machine>)
  ,public_key         TEXT CHECK (public_key IS NULL OR length(public_key) BETWEEN 43 AND 45)
  ,mtu                INTEGER
  ,fwmark             INTEGER
  ,dns_mode           TEXT NOT NULL DEFAULT 'none' CHECK (dns_mode IN ('none','static'))
  ,dns_servers        TEXT
  ,autostart          INTEGER NOT NULL DEFAULT 0
);

-- Server (one or more remote peers for an Iface)
CREATE TABLE IF NOT EXISTS Server (
  id                 INTEGER PRIMARY KEY
  ,created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
  ,updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
  ,iface_id           INTEGER NOT NULL REFERENCES Iface(id) ON DELETE CASCADE
  ,name               TEXT NOT NULL                 -- e.g. 'x6', 'US'
  ,public_key         TEXT NOT NULL CHECK (length(public_key) BETWEEN 43 AND 45)
  ,preshared_key      TEXT CHECK (preshared_key IS NULL OR length(preshared_key) BETWEEN 43 AND 45)
  ,endpoint_host      TEXT NOT NULL
  ,endpoint_port      INTEGER NOT NULL CHECK (endpoint_port BETWEEN 1 AND 65535)
  ,allowed_ips        TEXT NOT NULL                 -- typically '0.0.0.0/0'
  ,keepalive_s        INTEGER
  ,route_allowed_ips  INTEGER NOT NULL DEFAULT 1
  ,priority           INTEGER NOT NULL DEFAULT 100
  ,UNIQUE(iface_id, name)
);

-- Route (optional extra routes applied by post-up script)
CREATE TABLE IF NOT EXISTS Route (
  id                 INTEGER PRIMARY KEY
  ,created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
  ,updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
  ,iface_id           INTEGER NOT NULL REFERENCES Iface(id) ON DELETE CASCADE
  ,cidr               TEXT NOT NULL
  ,via                TEXT
  ,table_name         TEXT
  ,metric             INTEGER
  ,on_up              INTEGER NOT NULL DEFAULT 1
  ,on_down            INTEGER NOT NULL DEFAULT 0
);

-- User (many linux users → one Iface)
-- each user is bound to an iface via an 'ip rule add uidrange ..' command
CREATE TABLE IF NOT EXISTS User (
  id         INTEGER PRIMARY KEY
  ,created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
  ,updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
  ,iface_id   INTEGER NOT NULL REFERENCES Iface(id) ON DELETE CASCADE
  ,username   TEXT NOT NULL
  ,uid        INTEGER  -- cached UID if resolved
  ,UNIQUE(iface_id, username)
);

-- Effective view (provides computed defaults like rt_table_name_eff)
CREATE VIEW IF NOT EXISTS v_iface_effective AS
SELECT
  i.id
  ,i.iface
  ,COALESCE(i.rt_table_name, i.iface) AS rt_table_name_eff
  ,i.local_address_cidr
FROM Iface i;

-- mtime triggers
CREATE TRIGGER IF NOT EXISTS trg_iface_mtime
AFTER UPDATE ON Iface FOR EACH ROW
BEGIN
  UPDATE Iface
     SET updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
   WHERE id=NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_server_mtime
AFTER UPDATE ON Server FOR EACH ROW
BEGIN
  UPDATE Server
     SET updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
   WHERE id=NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_route_mtime
AFTER UPDATE ON Route FOR EACH ROW
BEGIN
  UPDATE Route
     SET updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
   WHERE id=NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_user_binding_mtime
AFTER UPDATE ON User FOR EACH ROW
BEGIN
  UPDATE User
     SET updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
   WHERE id=NEW.id;
END;
