# seedance-2-0-prompts — Install Guide

## Requirements

- Python 3.9+ (no pip install needed — stdlib only)

## Install Patterns

### Pattern A — Claude Code only

```powershell
$dest = "$env:USERPROFILE\.claude\skills"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force .\seedance-2-0-prompts $dest
```

### Pattern B — Codex CLI only

```powershell
$dest = "$env:USERPROFILE\.codex\skills"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force .\seedance-2-0-prompts $dest
# If Codex doesn't auto-detect, run with: codex --enable skills
```

### Pattern C — Build-once, use-twice (RECOMMENDED — symlink)

```powershell
# Place canonical copy at C:\skills\seedance-2-0-prompts\
$canonical = "C:\skills\seedance-2-0-prompts"

New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.claude\skills\seedance-2-0-prompts" `
  -Target $canonical

New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.codex\skills\seedance-2-0-prompts" `
  -Target $canonical
```

> **Note:** Symlinks on Windows require either an elevated PowerShell session **or** Windows Developer Mode enabled (Settings → Privacy & security → For developers → Developer Mode = On).

## Verify Install

```powershell
Get-ChildItem "$env:USERPROFILE\.claude\skills\seedance-2-0-prompts"
Get-ChildItem "$env:USERPROFILE\.codex\skills\seedance-2-0-prompts"
```

## Search Tool Usage

```
python scripts/search.py "keyword"              # top 5 results
python scripts/search.py "keyword" --top 10    # top N
python scripts/search.py --author "KANA"       # filter by author
python scripts/search.py --min-length 1000     # long prompts only
python scripts/search.py --max-length 200      # short prompts only
python scripts/search.py --random 5            # random samples
python scripts/search.py "keyword" --json      # JSON output
```

Run from the skill folder: `cd seedance-2-0-prompts`

## Corpus Refresh

CSV is frozen at build time. To update: replace `references/seedance-prompts.csv` and re-run install.
