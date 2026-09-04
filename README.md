# We Counted Our Own Agent Bill Wrong by 3×

> **Agents don't pay to think. They pay to remember.**

![cost forensics](docs/img/agent-bill-hero.png)

Forensics on one real Claude Code session — 7 minutes, one code-review task, 257 lines of local logs:

**Counting by log entries inflates input 3.3× and decisions 3×, while 89% of input traffic — cache re-reads — is completely invisible.**

First, the elephant in the room: **the provider's bill is correct.** We reconciled against [ccusage](https://github.com/ryoppippi/ccusage) and it matches our deduplicated numbers to the token. What was wrong is hand-counting from logs. And that exposes the actual question:

> **Metering is solved. Diagnosis is not.** 89.3% of input traffic was cache re-reads. 30% of the bill was cold start. One command ate 16%. No tool surfaces any of this.

## Same log, two ledgers

| Counting method | API calls | Input tokens | Output tokens |
|---|---|---|---|
| By log entries (naive) | 33 | 339,088 | 16,245 |
| Dedup by `message.id` (real) | **11** | **103,616** | **6,734** |

## Where the money actually goes

Typical pricing ratios (fresh = 1, cache read = 0.1, output = 5):

| Component | Share |
|---|---|
| Fresh input — of which **cold start alone ≈ 30%** of the whole bill | ≈ 46% |
| Cache re-reads — the real shape of the context tax | ≈ 39% |
| Output — the last long reply alone was 31% of all output | ≈ 15% |

One sentence: **85% of the bill is memory operations** — loading context and re-reading history. Thinking is 15%. Under typical ratios, memory costs ~5.7× more than thinking.

## The 30-second self-test

Run it on your own `~/.claude/projects`, then go ask your current cost tool why its numbers differ:

```python
import json, glob
calls = {}
for fp in glob.glob('~/.claude/projects/*/*.jsonl'):
    for line in open(fp):
        r = json.loads(line)
        if r.get('type') != 'assistant': continue
        calls[r['message']['id']] = r['message']['usage']  # dedup by message.id
fresh = sum(u['input_tokens'] for u in calls.values())
cache = sum(u['cache_read_input_tokens'] for u in calls.values())
out   = sum(u['output_tokens'] for u in calls.values())
print(f"API calls: {len(calls)} | fresh: {fresh:,} | cache: {cache:,} ({cache/(fresh+cache):.0%}) | out: {out:,}")
```

## Interactive page

**[Live interactive version](https://qianjinguo.github.io/agent-memory-tax/)** (English; [中文版](https://qianjinguo.github.io/agent-memory-tax/zh.html)) — one click toggles between the naive and honest ledger, plus the full "what we claim / what we don't" list. `?mode=honest` deep-links the honest ledger.

| Naive ledger | Honest ledger |
|---|---|
| ![naive](docs/img/agent-bill-naive.png) | ![honest](docs/img/agent-bill-honest.png) |

## Full write-up

[article.zh.md](article.zh.md) (Chinese) — methodology and error bounds, the reconciliation experiment, and the multi-tool support matrix:

| Tool | Status |
|---|---|
| Claude Code | ✅ verified — usage four-piece + `message.id`, this post's calibration target |
| ZCode | ✅ verified — full request bodies + exact usage, CJK estimate error 0.97–1.02 |
| Codex CLI | ✅ verified — fresh / cache-read / cache-write split, reasoning tokens listed, plus 5h & weekly quota percent |
| OpenCode / pi agent / Hermes | ⚠ verified gaps — export required or no usage fields (volume estimation only) |
| Pure-cloud tools (e.g. DeepSeek web) | ✕ no local logs — hard boundary of the zero-integration method |

## Limitations (the honest section)

n=1. Pricing ratios are assumptions — logs contain tokens, not dollars. The GLM endpoint was proxied and `cache_creation` was always 0 (likely dropped by the proxy). The methodology is pinned to Claude Code v2.1.153; runtimes drift, so re-validate on upgrade.

中文完整版：[article.zh.md](article.zh.md)

## License

MIT
