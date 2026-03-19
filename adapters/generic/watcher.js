#!/usr/bin/env node
/**
 * Generic file watcher adapter for moonshine.
 *
 * Watches a directory for .jsonl transcript files and feeds new lines
 * to the observer pipeline for automatic memory extraction.
 *
 * Usage:
 *   MOONSHINE_WATCH_DIR=/path/to/transcripts node watcher.js
 *
 * Environment:
 *   MOONSHINE_WATCH_DIR  — directory to watch (required)
 *   OBSERVER_DB          — path to observations.db (default: ./observations.db)
 *   ANTHROPIC_API_KEY    — for observer LLM calls
 */

import { watch, readFileSync, statSync } from "fs";
import { join, basename } from "path";
import { execSync } from "child_process";

const WATCH_DIR = process.env.MOONSHINE_WATCH_DIR;
if (!WATCH_DIR) {
  console.error(
    "Error: MOONSHINE_WATCH_DIR environment variable is required."
  );
  console.error(
    "Usage: MOONSHINE_WATCH_DIR=/path/to/transcripts node watcher.js"
  );
  process.exit(1);
}

const OBSERVER_SCRIPT =
  process.env.OBSERVER_SCRIPT ||
  join(import.meta.dirname, "..", "..", "observer", "observe.js");
const fileOffsets = new Map();

function processNewLines(filepath) {
  try {
    const stat = statSync(filepath);
    const prevSize = fileOffsets.get(filepath) || 0;

    if (stat.size <= prevSize) return;

    const content = readFileSync(filepath, "utf8");
    const lines = content.split("\n").filter((l) => l.trim());
    const prevLines = fileOffsets.has(filepath)
      ? Math.max(
          0,
          content.substring(0, prevSize).split("\n").filter((l) => l.trim())
            .length
        )
      : 0;

    const newLines = lines.slice(prevLines);
    fileOffsets.set(filepath, stat.size);

    if (newLines.length === 0) return;

    const sessionId =
      basename(filepath, ".jsonl") || `session-${Date.now()}`;

    for (const line of newLines) {
      try {
        const msg = JSON.parse(line);
        if (!msg.role || !msg.content) continue;

        console.log(
          `[${sessionId}] ${msg.role}: ${msg.content.substring(0, 80)}...`
        );
        // Messages accumulate in the observer DB; the observer fires
        // when the unobserved token threshold is crossed.
      } catch {
        // Skip malformed lines
      }
    }

    console.log(
      `[${sessionId}] Processed ${newLines.length} new line(s) from ${basename(filepath)}`
    );
  } catch (err) {
    console.error(`Error processing ${filepath}: ${err.message}`);
  }
}

console.log(`👁️ Watching ${WATCH_DIR} for .jsonl transcripts...`);

watch(WATCH_DIR, (eventType, filename) => {
  if (!filename || !filename.endsWith(".jsonl")) return;
  const filepath = join(WATCH_DIR, filename);
  processNewLines(filepath);
});

// Initial scan
import { readdirSync } from "fs";
for (const file of readdirSync(WATCH_DIR)) {
  if (file.endsWith(".jsonl")) {
    const filepath = join(WATCH_DIR, file);
    const stat = statSync(filepath);
    fileOffsets.set(filepath, stat.size);
    console.log(`  Tracking: ${file} (${stat.size} bytes)`);
  }
}

console.log(`Ready. Waiting for new transcript data...`);
