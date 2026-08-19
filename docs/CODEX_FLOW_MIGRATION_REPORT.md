# Codex Flow Migration Report

Date: 2026-08-19

## Migrated

- `architectural-assembly-reveal`: migrated from `Codex_CS`
- `city-real-estate-habitat-promo`: migrated from `Codex_CS`
- `dawn-mist-aerial-real-estate`: migrated from `Codex_CS`
- `giant-ip-landmark-parade`: migrated from `Codex_CS`
- `sci-fi-city-promo`: migrated from `Codex_CS`
- `scene-storyboard-grid`: migrated from `Codex_IS`

## Blocked

None.

## Merged

- `giant-3d-logo-landmark-video`: deprecated because the latest legacy
  `intake-report.json` is `ready_for_approval` with
  `user_approval.approved=false`. It is not installed in the Codex Flow
  business-skill library.

## Deprecated

None.

## Registry Command

```powershell
python packages/Codex_Flow/platform/cli.py build
```

The compiled registry is written under `packages/Codex_Flow/.codex-flow-private/`,
which is ignored by Git.
