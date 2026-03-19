-- Long-Term Memory Database Schema
-- Created: 2026-02-11

-- Core memories table
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  
  -- Classification
  type TEXT NOT NULL CHECK (type IN ('event', 'lesson', 'person', 'behavior', 'project', 'insight', 'decision', 'preference', 'skill')),
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  
  -- Flexible metadata
  metadata TEXT DEFAULT '{}',
  tags TEXT DEFAULT '[]',
  
  -- Ranking
  importance INTEGER DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
  
  -- Provenance
  source TEXT,
  source_date DATE,
  archived_from TEXT,
  
  -- Relationships
  related_ids TEXT DEFAULT '[]',
  
  -- Timestamps
  created_at TEXT DEFAULT (datetime('now', 'localtime')),
  updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Embeddings table (separate for clean updates)
CREATE TABLE IF NOT EXISTS embeddings (
  memory_id INTEGER PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
  embedding BLOB NOT NULL,
  model TEXT NOT NULL DEFAULT 'nomic-embed-text',
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_source_date ON memories(source_date DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);

-- Full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
  title, 
  content, 
  tags,
  content='memories',
  content_rowid='id'
);

-- FTS sync triggers
CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, title, content, tags) 
  VALUES (new.id, new.title, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, title, content, tags) 
  VALUES ('delete', old.id, old.title, old.content, old.tags);
  INSERT INTO memories_fts(rowid, title, content, tags) 
  VALUES (new.id, new.title, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, title, content, tags) 
  VALUES ('delete', old.id, old.title, old.content, old.tags);
END;

-- ============ Entity System ============

-- Entities are first-class objects (people, projects, tools, concepts)
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    aliases TEXT DEFAULT '[]',
    description TEXT,
    first_seen TEXT,
    last_seen TEXT,
    memory_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_name_type ON entities(name, type);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);

-- Junction table: which entities appear in which memories
CREATE TABLE IF NOT EXISTS memory_entities (
    memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'mention',
    confidence REAL DEFAULT 1.0,
    PRIMARY KEY (memory_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_me_entity ON memory_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_me_memory ON memory_entities(memory_id);

-- ============ Memory Graph (Edges) ============

CREATE TABLE IF NOT EXISTS memory_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    metadata TEXT DEFAULT '{}',
    UNIQUE(source_id, target_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON memory_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON memory_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON memory_edges(edge_type);

-- Update timestamp trigger
CREATE TRIGGER IF NOT EXISTS memories_updated AFTER UPDATE ON memories BEGIN
  UPDATE memories SET updated_at = datetime('now', 'localtime') WHERE id = new.id;
END;
