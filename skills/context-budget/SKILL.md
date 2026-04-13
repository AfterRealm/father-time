---
name: context-budget
description: Estimate the token cost of reading a file or directory before doing it. Use when asking "how many tokens would this cost", "how big is this file in tokens", or before reading large files.
license: MIT
metadata:
  author: AfterRealm
  version: "1.8.3"
---

# Context Budget — Token Estimation

Estimate how many tokens a file or directory will consume before reading it.

## How to Estimate

**Rule of thumb:** 1 token ≈ 4 characters (English text/code). This is a rough estimate.

When the user asks about a file or directory:

1. Get the file size in bytes using:
```bash
wc -c < "filepath"
```
Or for a directory:
```bash
find "dirpath" -type f -exec wc -c {} + | tail -1
```

2. Estimate tokens: `file_size_bytes / 4`

3. Show the estimate with context AND model comparison:

```
File: path/to/file.py
Size: 12,400 bytes
Est. tokens: ~3,100
Context impact: 0.3% of 1M window

Cost to read (first time / cached):
  Opus:   $0.047 / $0.005
  Sonnet: $0.009 / $0.001
  Haiku:  $0.002 / $0.0002
```

Use these prices per 1M tokens for the comparison:

| Model | Input | Cache Read | Cache Write | Output |
|-------|-------|------------|-------------|--------|
| Opus 4.6 | $5.00 | $0.50 | $6.25 | $25.00 |
| Sonnet 4.6 | $3.00 | $0.30 | $3.75 | $15.00 |
| Haiku 4.5 | $1.00 | $0.10 | $1.25 | $5.00 |

- "First time" = input price (first read, not yet cached)
- "Cached" = cache read price (subsequent reads in same session)
- Always show all three models so users can compare

For directories, also show file count and breakdown of largest files.

## Context Impact Table

| Tokens | % of 1M | % of 200K | Verdict |
|--------|---------|-----------|---------|
| < 1K | 0.1% | 0.5% | Trivial |
| 1-5K | 0.1-0.5% | 0.5-2.5% | Light |
| 5-20K | 0.5-2% | 2.5-10% | Moderate |
| 20-50K | 2-5% | 10-25% | Heavy — consider reading specific sections |
| 50K+ | 5%+ | 25%+ | Very heavy — read only what you need |

## Tips

- Suggest `--offset` and `--limit` on Read for large files
- For directories, suggest reading only the files that matter
- Minified JS/CSS files are token-dense — warn about them
- Binary files waste tokens — flag them
