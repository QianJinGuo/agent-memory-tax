# We Counted Our Own Agent Bill Wrong by 3×

*Full write-up. 中文完整版：[article.zh.md](article.zh.md). Interactive version: [qianjinguo.github.io/agent-memory-tax](https://qianjinguo.github.io/agent-memory-tax/).*

We ran a cost forensic on one real Claude Code session: 7 minutes, one code-review task, 257 lines of local logs. Putting "what it looks like" next to "what was actually billed" — **counting the way cost reports count inflated this session's input 3.3×, its decision count 3×, and completely missed the thing that was 89% of input traffic.**

This is not a bug in any particular tool. It is a structural blind spot shared by every cost report that counts by log entries.

Let's get the subject right first: **the provider's bill is correct.** The vendor charges by real billing semantics — full-price input, cache reads at roughly 1/10, output — never a cent more. What was wrong is the private ledger we recomputed from logs: treat duplicate streaming records as separate calls, sum `input_tokens` directly, ignore the cache fields, and your recomputed number comes out 3× higher than what was actually billed. Our own hand-counting is the living specimen of this failure.

We then reconciled the same session against [ccusage](https://github.com/ryoppippi/ccusage), and it matched our deduplicated numbers **token for token**: input 103,616, output 6,734, cache read 866,560. Mature metering is fine. Which leads to this post's actual question: **metering is solved; diagnosis is not.** Cache share 89.3%, cold start 30% of the bill, one command eating 16% — no mainstream tool surfaces these as first-class outputs. There have been attempts ([retok](https://github.com/d-date/retok) built a genuinely complete set of diagnostic rules), but they never became mainstream, and ccusage's default output has no place for them.

## The subject

- Source: a real session JSONL under `~/.claude/projects/` (257 lines)
- Task: one code review (a private repo — this repo is its public reproduction)
- Model: glm-5-3-flash (proxied through Claude Code)
- What the UI showed: 33 conversation turns, 7 minutes

## Finding 1: the 33 turns are fake — there were only 11 API calls

The log contains 33 assistant records, but each record's `usage` (input/output tokens) is booked **per API response** — one streaming response is split into 2–4 records, each carrying the same usage snapshot. The real dedup key is `message.id`:

| Counting method | Calls |
|---|---|
| By log entries (how most reports count) | 33 |
| Dedup by `message.id` (actual billed calls) | **11** |

If you have ever looked at a "cost per decision" report, ask one question first: did it dedup?

## Finding 2: the real billed input is 103,616 — not 339,088

Summing `input_tokens` across all 33 records gives 339,088 — a phantom produced by double-counting. Deduplicated:

| Metric | Naive sum | Dedup by `message.id` |
|---|---|---|
| fresh input | 339,088 | **103,616** |
| output | 16,245 | **6,734** |
| API calls | 33 | **11** |

## Finding 3: 89.3% of input traffic is cache hits — invisible in every billing narrative

After dedup, the session's true input traffic is 103,616 (fresh) + 866,560 (`cache_read_input_tokens`) = 970,176 tokens. **Cache hits are 89.3% of it.**

This is the real structure of agent cost: you pay full price once at session start (the first call billed 66,609 tokens with cache at zero), and every later turn pays full price only for the increment while re-reading the entire history at roughly 1/10. Context grew from 66.6K to 104K (+56%) — the "context tax" is real, but its rate is 0.1, not 1.

## So where did the money go

No price table is embedded in the logs, so with typical ratios (fresh input = 1, cache read = 0.1, output = 5), the bill's structure:

- **Fresh input ≈ 46%** — of which **cold start alone ≈ 30% of the whole bill** (the first call's unavoidable full price of 66K)
- **Cache re-reads ≈ 39%** — the real shape of the context tax: mild, but rising every turn
- **Output ≈ 15%** — the final long reply alone was 31% of all output

One line: **85% of the bill is memory operations** — loading context and reading history back. The product of thinking is 15%. Under typical ratios, memory costs ~5.7× more than thinking.

One anomaly also stands out: call #5 had a single Bash result inject 27,189 full-price tokens — one command eating ~16% of the entire bill. Big-output commands like `git diff` are the classic hidden fat order of agent cost.

The actionable consequence flips too: **the lever is not "chat fewer turns" but "don't let tool results explode"** (targeted reads instead of full `cat`/`diff` dumps) and "start a fresh session per task" (stop dragging 100K tokens of history into every new job). This matches, at log-level evidence, the six-blade cost optimization playbook described in Alibaba's Bailian cost-reduction write-up — and agent token consumption already exceeds humans' 5.2× (OpenRouter data), so this waste multiplies across the industry's bills.

## The 30-second self-test

Run it on your own `~/.claude/projects`, then go ask your current cost tool why its numbers differ:

```bash
python3 - <<'EOF'
import json, glob, os
calls = {}
for fp in glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl')):
    for line in open(fp, encoding='utf-8'):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('type') != 'assistant':
            continue
        m = r.get('message') or {}
        u = m.get('usage')
        if not (m.get('id') and u):
            continue
        calls[m['id']] = u  # dedup by message.id
fresh = sum(u.get('input_tokens', 0) for u in calls.values())
cache = sum(u.get('cache_read_input_tokens', 0) for u in calls.values())
out   = sum(u.get('output_tokens', 0) for u in calls.values())
print(f"API calls: {len(calls)} | fresh: {fresh:,} | cache: {cache:,} ({cache/(fresh+cache):.0%}) | out: {out:,}")
EOF
```

(Also available as a file: [count.py](count.py) — same logic, no copy-paste needed.)

## Does this hold on other tools

Yes — the general part is the **three-step method** (locate the local log directory → dedup by call id → split tokens into fresh / cache-read / output buckets). Every tool is just a few dozen lines of schema adapter on top, because the invariant underneath is the usage semantics shared by Anthropic-lineage and OpenAI-lineage APIs. ccusage supporting eight tools already proves the adapter logistics are tractable. Verified first-hand on this machine:

| Tier | Tools | Status |
|---|---|---|
| 1: full fields | Claude Code | ✅ verified — usage four-piece + `message.id`; this post's calibration target |
| 1: full fields | ZCode | ✅ verified — full request bodies + exact usage; CJK-aware estimate error 0.97–1.02 |
| 1: full fields | Codex CLI | ✅ verified — `token_count` events carry fresh / cache-read / cache-write, reasoning tokens listed, plus 5h & weekly quota percent |
| 2: gaps | OpenCode | ⚠ verified — local storage exposes no usage; standard route requires `opencode export` |
| 2: gaps | pi agent, Hermes | ⚠ verified/untested — Hermes sessions are plain conversation without usage fields (volume estimation only); pi untested |
| 3: boundary | Pure-cloud tools (e.g. DeepSeek web) | ❌ no local logs — the physical boundary of the zero-integration method |

## Three rules for anyone building a cost tool

1. **Dedup by `message.id`** — log entries ≠ billed calls; streaming responses are recorded 2–4 times.
2. **Split the cache** — `input_tokens` is only the full-price part; `cache_read_input_tokens` is another order of magnitude at another price. A "total input" that doesn't split cache is meaningless.
3. **Price per model** — logs contain tokens, not money; a new model is a new price sheet.

And the honest competitive coordinate: [retok](https://github.com/d-date/retok) is the furthest predecessor in this direction — seven rule-based diagnoses (cache-TTL re-caching, oversized contexts, retry loops, under-delegation…), zero-dependency Python, shipped 2026-07. Its quietness (33 stars in five months) is itself part of this post's conclusion: **the demand for diagnosis exists, but "install yet another analyzer" as a distribution form has not been accepted by the market** — the same fact as "no mainstream tool ships diagnosis in its default output," seen from the other side.

## Methodology and error bounds

Layered explicitly: **token counts are the fact layer** (usage fields reported by the runtime; this post only dedups and sums); **dollars and shares are the inference layer** (a function of assumed price ratios). The two have different confidence, and citing them interchangeably is where accountings go wrong.

- **Dedup safety**: duplicate records sharing one `message.id` had fully consistent usage (11 ids, 0 mismatches) — dedup introduces no error.
- **Split fuzziness**: the fresh/cache-read boundary is set by system cache breakpoints, not content boundaries — a conservation check showed ±a few hundred tokens of per-call fuzz (0.2–2% of context). So this post only draws conclusions at magnitudes far above the noise (cold start 30%, the single 27K fat order), never exact per-call attribution.
- **Version pinning**: verified on Claude Code v2.1.153; a runtime update can shift log formats — re-validate per version.
- **No bill reconciliation**: we could not obtain a vendor-side bill as ground truth (the GLM endpoint was proxied and `cache_creation` stayed 0 — the proxy likely dropped the field, which means the real bill may differ from our estimate again). Readers with API bills can reconcile using the script above.
- **n=1**: we claim this session's structure, not an industry distribution.

## Limitations

One sample (1 session, 1 model, 1 harness). Typical ratios are assumptions; dollar conversion needs per-model pricing tables. The structure of the conclusions (dedup, cache share, cold-start share) should hold across sessions; the specific percentages will float.

---

*Data and reproduction: the agent-memory-tax repo (2026-09). Subject session `d823d9e5`; cross-checked with ccusage token-for-token.*
