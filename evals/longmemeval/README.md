# LongMemEval Benchmark Harness

Benchmarks the moonshine memory system against [LongMemEval](https://github.com/xiaowu0162/LongMemEval) (ICLR 2025) — 500 questions testing long-term memory across 5 capabilities:

- **Single-session extraction** (user, assistant, preference)
- **Multi-session reasoning**
- **Knowledge updates**
- **Temporal reasoning**

## How It Works

For each question, the harness:

1. Creates a fresh SQLite database using the moonshine schema
2. Ingests all conversation sessions as memories (FTS5-indexed)
3. Searches the memory DB using FTS5 keyword search
4. Sends retrieved context + question to Claude for answering
5. Appends the hypothesis to a JSONL file

## Setup

```bash
npm install
```

Requires `ANTHROPIC_API_KEY` in environment or `~/.env.anthropic`.

## Usage

```bash
# Quick test (5 questions, oracle dataset)
node harness.js --dataset oracle --limit 5

# Quick test (10 questions)
node harness.js --dataset oracle --limit 10

# Full oracle run (ceiling test — only evidence sessions)
node harness.js --dataset oracle

# Full benchmark run (~40 sessions per question)
node harness.js --dataset s

# Resume from question 200
node harness.js --dataset oracle --start 200

# Use a different model
node harness.js --dataset oracle --model claude-sonnet-4-20250514

# Or via env var
EVAL_MODEL=claude-sonnet-4-20250514 node harness.js --dataset oracle
```

## Evaluation

Uses the exact LongMemEval evaluation prompts (LLM-as-judge, type-specific prompts).

```bash
# Evaluate with Claude as judge (default: claude-sonnet-4-20250514)
node evaluate.js hypotheses-oracle.jsonl --judge anthropic

# Evaluate with GPT-4o as judge
node evaluate.js hypotheses-oracle.jsonl --judge openai

# Evaluate the S dataset hypotheses
node evaluate.js hypotheses-s.jsonl --dataset s --judge anthropic
```

Outputs:
- `hypotheses-{dataset}.jsonl.eval-{judge}.jsonl` — per-question evaluation log
- `hypotheses-{dataset}.jsonl.eval-{judge}-summary.json` — aggregate results

## Data

- `data/longmemeval_oracle.json` — 500 questions with only evidence sessions (15MB)
- `data/longmemeval_s.json` — 500 questions with ~40-session haystacks (265MB)

Downloaded from [HuggingFace](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned).

## Architecture

```
harness.js     → Ingest + Search + Generate hypotheses
evaluate.js    → LLM-as-judge scoring with LongMemEval prompts
core/schema.sql → Moonshine memory schema (SQLite + FTS5)
```

The harness is **resumable**: existing hypotheses in the output file are skipped automatically.
Use `--start N` for explicit offset-based resumption.
