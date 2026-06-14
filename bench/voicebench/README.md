# `bench/voicebench` — VoiceBench reproduction harness

Reproduction script for running [VoiceBench (TACL'26)] against an
Àkàndé provider × model configuration. The harness stops short of
the upstream LLM-as-judge step so per-configuration numbers can be
diffed cheaply.

---

## What this gives you

- `run.py` — single-threaded scorer that walks a VoiceBench JSONL
  prompts file and writes a per-row + aggregated JSON report
  (latency, OK-rate, response length).
- `results/` — committed results so the project README can quote
  numbers without rerunning anything.

The upstream harness adds an LLM-as-judge pass on top of the
collected responses. This runner deliberately stops at response
collection so the same JSON can be diffed across providers, models,
or cost setups without paying for the judge run each time. Pipe
the JSON through the upstream evaluator when you want the
public-facing leaderboard score.

---

## Reproducing

```bash
# 1. Clone the upstream prompt set (one-off).
git clone https://github.com/matthewcym/voicebench /tmp/vb

# 2. Score a configuration.  --limit truncates the prompt set to
#    the first N rows; drop it for the full sweep.
python bench/voicebench/run.py \
    --prompts /tmp/vb/all.jsonl \
    --provider openai --model gpt-4o-mini \
    --output bench/voicebench/results/openai-gpt4o-mini.json \
    --limit 100

# 3. Inspect the headline summary.
jq '.summary.overall' bench/voicebench/results/openai-gpt4o-mini.json
```

### Comparing two configurations

```bash
# Diff two providers on the same prompt set.
diff \
  <(jq '.summary.overall' results/openai-gpt4o-mini.json) \
  <(jq '.summary.overall' results/anthropic-claude-3-haiku.json)
```

---

## Provider sweep

The five baselines tracked for the project README leaderboard:

| Provider  | Model                        | Output                                             |
|-----------|------------------------------|----------------------------------------------------|
| openai    | `gpt-4o-mini`                | `results/openai-gpt4o-mini.json`                   |
| openai    | `gpt-4o`                     | `results/openai-gpt4o.json`                        |
| anthropic | `claude-3-haiku-20240307`    | `results/anthropic-claude-3-haiku.json`            |
| google    | `gemini-1.5-flash`           | `results/google-gemini-1.5-flash.json`             |
| groq      | `llama3-70b-8192`            | `results/groq-llama3-70b.json`                     |

Each row is reproducible with the command in [Reproducing](#reproducing)
by swapping `--provider` and `--model`. Re-run the matrix whenever a
provider SDK pin moves in `pyproject.toml`.

[VoiceBench (TACL'26)]: https://arxiv.org/pdf/2410.17196
