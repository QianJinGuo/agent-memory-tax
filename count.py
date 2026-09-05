#!/usr/bin/env python3
"""30-second self-test: count your agent bill the honest way.
Dedups Claude Code logs by message.id and splits tokens into
fresh / cache-read / output buckets. Python 3.7+, stdlib only."""
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
