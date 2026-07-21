CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, query TEXT NOT NULL, template TEXT NOT NULL, language TEXT NOT NULL,
  require_plan_approval INTEGER NOT NULL DEFAULT 0,
  llm_provider TEXT, llm_model TEXT, search_provider TEXT, crawl_provider TEXT,
  status TEXT NOT NULL, title TEXT, report_markdown TEXT, error TEXT,
  owner_id TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sections (
  run_id TEXT NOT NULL, id TEXT NOT NULL, idx INTEGER NOT NULL,
  title TEXT, goal TEXT, queries_json TEXT, summary TEXT, status TEXT,
  PRIMARY KEY (run_id, id)
);
CREATE TABLE IF NOT EXISTS sources (
  run_id TEXT NOT NULL, ref_num INTEGER NOT NULL, section_id TEXT,
  title TEXT, url TEXT, snippet TEXT, PRIMARY KEY (run_id, ref_num)
);
CREATE TABLE IF NOT EXISTS events (
  run_id TEXT NOT NULL, seq INTEGER NOT NULL, type TEXT NOT NULL,
  data_json TEXT NOT NULL, ts INTEGER NOT NULL, PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
-- Security (M3): encrypted provider credentials + audit trail.
CREATE TABLE IF NOT EXISTS provider_credentials (
  id TEXT PRIMARY KEY, provider TEXT NOT NULL, label TEXT NOT NULL,
  ciphertext BLOB NOT NULL, nonce BLOB NOT NULL, key_version INTEGER NOT NULL,
  masked_hint TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
  created_by TEXT, created_at TEXT NOT NULL, expires_at TEXT, last_used_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id TEXT PRIMARY KEY, actor_id TEXT, action TEXT NOT NULL,
  target_type TEXT, target_id TEXT, meta_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  password_hash TEXT, google_sub TEXT UNIQUE, role TEXT NOT NULL,
  disabled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL, revoked_at TEXT, user_agent TEXT, created_at TEXT NOT NULL
);
-- Engine v2 (M3.5): claim-grounded verification.
CREATE TABLE IF NOT EXISTS claims (
  run_id TEXT NOT NULL, id TEXT NOT NULL, section_id TEXT,
  text TEXT NOT NULL, entity TEXT, attribute TEXT, quote TEXT, stance TEXT,
  created_at TEXT NOT NULL, PRIMARY KEY (run_id, id)
);
CREATE TABLE IF NOT EXISTS claim_sources (
  run_id TEXT NOT NULL, claim_id TEXT NOT NULL, ref_num INTEGER NOT NULL,
  PRIMARY KEY (run_id, claim_id, ref_num)
);
CREATE TABLE IF NOT EXISTS verifications (
  run_id TEXT NOT NULL, claim_id TEXT NOT NULL,
  verdict TEXT NOT NULL, confidence REAL, rationale TEXT, verifier_model TEXT,
  created_at TEXT NOT NULL, PRIMARY KEY (run_id, claim_id)
);
CREATE TABLE IF NOT EXISTS contradictions (
  run_id TEXT NOT NULL, id TEXT NOT NULL, entity TEXT, attribute TEXT,
  claim_id_a TEXT NOT NULL, claim_id_b TEXT NOT NULL, note TEXT,
  PRIMARY KEY (run_id, id)
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claims_run ON claims(run_id, section_id);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, seq);
CREATE INDEX IF NOT EXISTS idx_cred_provider ON provider_credentials(provider, status);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);
