CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, query TEXT NOT NULL, template TEXT NOT NULL, language TEXT NOT NULL,
  require_plan_approval INTEGER NOT NULL DEFAULT 0,
  llm_provider TEXT, llm_model TEXT, search_provider TEXT, crawl_provider TEXT,
  status TEXT NOT NULL, title TEXT, report_markdown TEXT, error TEXT,
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
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, seq);
