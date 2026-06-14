# VoiceBench

Reproduction script for running [VoiceBench (TACL'26)] against an
Àkàndé pipeline configuration.

## What this gives you

- `run.py` — a single-threaded scorer that walks a VoiceBench
  JSONL prompts file and writes a per-row + aggregated JSON
  report (latency, OK-rate, response length).
- `results/` — committed results so the README can quote numbers
  without rerunning anything.

The official VoiceBench harness also runs an LLM-as-judge step on
top of the model responses; this runner stops at the response
collection so the numbers can be diffed across providers / models /
cost setups without paying for the judge run each time.  Pipe the
JSON through the upstream evaluator when you want the
public-facing leaderboard score.

## Reproducing

```bash
# 1. Clone the prompts (do this once)
git clone https://github.com/matthewcym/voicebench /tmp/vb

# 2. Score a configuration
python bench/voicebench/run.py \
    --prompts /tmp/vb/all.jsonl \
    --provider openai --model gpt-4o-mini \
    --output bench/voicebench/results/openai-gpt4o-mini.json \
    --limit 100         # drop --limit for the full sweep

# 3. Inspect the summary
jq '.summary.overall' bench/voicebench/results/openai-gpt4o-mini.json
```

## Provider sweep

We track five baselines for the README leaderboard:

| Provider  | Model                      | Output |
|-----------|----------------------------|--------|
| openai    | gpt-4o-mini                | results/openai-gpt4o-mini.json |
| openai    | gpt-4o                     | results/openai-gpt4o.json |
| anthropic | claude-3-haiku-20240307    | results/anthropic-haiku.json |
| google    | gemini-1.5-flash           | results/google-flash.json |
| groq      | llama3-70b-8192            | results/groq-llama3-70b.json |

[VoiceBench (TACL'26)]: https://arxiv.org/pdf/2410.17196
