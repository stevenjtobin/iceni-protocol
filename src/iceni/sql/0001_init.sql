-- ICENI v0.1 core schema (migration 0001)
-- Resolution chain:  petname -> canonical_id -> signed alias_version -> per-model render
-- The NAME is never the trust anchor; the signed, content-addressed intent is.

PRAGMA journal_mode = WAL;

-- Layer 2: cryptographic identities (self-certifying key, or DNS-anchored web)
CREATE TABLE IF NOT EXISTS identities (
  canonical_id TEXT PRIMARY KEY,             -- 'aip:key:ed25519:<multibase>' | 'aip:web:<domain>/<path>'
  kind         TEXT NOT NULL CHECK (kind IN ('key','web')),
  public_key   BLOB,                          -- Ed25519 raw pubkey (kind='key')
  created_at   TEXT NOT NULL,
  meta_json    TEXT
);

-- Layer 1: KERI-style append-only key-event log (inception/rotation/revocation), hash-chained
CREATE TABLE IF NOT EXISTS key_events (
  canonical_id TEXT NOT NULL REFERENCES identities(canonical_id),
  seq          INTEGER NOT NULL,
  event_type   TEXT NOT NULL CHECK (event_type IN ('inception','rotation','revocation')),
  prior_digest TEXT,
  digest       TEXT NOT NULL,
  signature    BLOB NOT NULL,
  created_at   TEXT NOT NULL,
  PRIMARY KEY (canonical_id, seq)
);

-- Layer 3: LOCAL petname binding — the anti-masquerade primitive. NEVER synced.
CREATE TABLE IF NOT EXISTS petnames (
  petname      TEXT NOT NULL,                 -- 'review' (the human types this)
  canonical_id TEXT NOT NULL REFERENCES identities(canonical_id),
  scope        TEXT NOT NULL DEFAULT 'user',  -- 'user' | 'project:<path>'
  created_at   TEXT NOT NULL,
  PRIMARY KEY (petname, scope)
);

-- The model-agnostic intent, content-addressed (sha256) + SemVer-of-intent, Ed25519-signed
CREATE TABLE IF NOT EXISTS alias_versions (
  content_hash TEXT PRIMARY KEY,             -- sha256(canonical intent json)
  canonical_id TEXT NOT NULL REFERENCES identities(canonical_id),
  semver       TEXT NOT NULL,                 -- MAJOR.MINOR.PATCH of INTENT
  intent_json  TEXT NOT NULL,
  parent_hash  TEXT,                          -- DAG link for history
  vclock_json  TEXT NOT NULL,                 -- dotted-version vector
  signature    BLOB NOT NULL,
  created_at   TEXT NOT NULL,
  deleted_at   TEXT                           -- soft-delete audit trail (Kimi review)
);
CREATE INDEX IF NOT EXISTS ix_alias_versions_id_semver ON alias_versions(canonical_id, semver);

-- Per-model rendered prompts (calibration output) — claude / gpt / kimi / ...
CREATE TABLE IF NOT EXISTS model_templates (
  content_hash    TEXT NOT NULL REFERENCES alias_versions(content_hash),
  model           TEXT NOT NULL,
  rendered_prompt TEXT NOT NULL,
  calibrated_at   TEXT NOT NULL,
  calib_source    TEXT NOT NULL DEFAULT 'engine',   -- 'engine' | 'manual' | 'evolved'
  PRIMARY KEY (content_hash, model)
);

-- Execution feedback (the value-case telemetry: V1 consistency, V2 tokens/cost, V4 quality)
CREATE TABLE IF NOT EXISTS executions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  content_hash TEXT NOT NULL REFERENCES alias_versions(content_hash),
  model        TEXT NOT NULL,
  outcome      TEXT,                          -- 'accepted' | 'edited' | 'rejected'
  user_edit    TEXT,
  tokens_in    INTEGER,
  tokens_out   INTEGER,
  embedding    BLOB,
  created_at   TEXT NOT NULL
);

-- Drift state per alias (rolling scalar series + serialized ADWIN)
CREATE TABLE IF NOT EXISTS drift_state (
  canonical_id       TEXT PRIMARY KEY REFERENCES identities(canonical_id),
  scalar_series_json TEXT NOT NULL DEFAULT '[]',
  adwin_state_json   TEXT,
  last_flag_at       TEXT,
  status             TEXT NOT NULL DEFAULT 'ok'  -- 'ok' | 'warning' | 'drifted'
);

-- Auto-discovery candidates awaiting BINARY accept/reject
CREATE TABLE IF NOT EXISTS discovery_candidates (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  intent_summary    TEXT NOT NULL,
  example_count     INTEGER NOT NULL,
  suggested_petname TEXT,
  status            TEXT NOT NULL DEFAULT 'pending',  -- 'pending'|'accepted'|'rejected'
  created_at        TEXT NOT NULL
);
