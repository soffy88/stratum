# Vendored: luobo-ppt

- Upstream: https://github.com/zhouwei713/luobo-ppt
- Commit: `b6dcb0f325b3ea38a7ca3cd3c211bbba7fb436b2` (2026-10-08)
- License: MIT (`LICENSE`); bundled Lucide icons are ISC (`assets/LICENSE-lucide.txt`).

## What is kept

`SKILL.md`, `README.md`, `LICENSE`, `scripts/`, `references/` (deck schema, layout
rules, the 14 style presets) and the runtime assets under `assets/` (icon sheet,
icon keywords, Lucide license). Left out: `docs/images/` (README screenshots),
`assets/style_gallery.jpg` (preset gallery image, only rebuilt by
`style_previews.py --sample --all`), installers and agent manifests.

## Local changes

None. The scripts are unmodified so the directory can be refreshed by copying a
newer upstream checkout over it. Stratum drives them as subprocesses from
`src/stratum/services/ppt_export/` and never imports them into the API process.

Excluded from Ruff (`pyproject.toml`, `extend-exclude`) because it is third-party
code kept byte-identical to upstream.
