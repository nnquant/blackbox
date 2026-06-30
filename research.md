# hypothesis
Increasing WebUI information density by tightening spacing, reducing oversized cards, and making dashboards more scan-friendly will improve daily operating efficiency without hiding primary controls.

## parent
main

## branch
exp-20260628-compact-front-layout

## change
- Inspect current WebUI layout hotspots.
- Compact page chrome, spacing, cards, lists, and management/dashboard surfaces where the code already has dense operational data.
- Keep existing routes, copy, data contracts, and visual language.

## expectation
Users can compare more projects, runs, metrics, and management signals in one viewport with less vertical scrolling.

## evaluation
- compare against main
- frontend build must pass
- inspect desktop layout through the local Vite app when possible
- avoid backend/API changes unless required by layout

## result
- Implemented compact shell/layout pass in `webui/src/App.jsx` and `webui/src/main.css`.
- Desktop verification at `http://127.0.0.1:5177/manage`: no horizontal overflow; header 48px, sidebar 224px, management stat tiles 6 per row at 1280px viewport.
- Mobile verification at 390px viewport: no horizontal overflow; management stat tiles use 2 columns without overflow expand buttons; bottom navigation uses 4 columns / 2 rows and height 118px.
- `npm run build` passed after rerun outside the Windows sandbox: 2410 modules transformed, built in 5.03s.
- Follow-up palette pass changed the base WebUI palette to black/white/gray across theme tokens, table chrome, neutral selected states, heatmaps, and chart default series colors while preserving colored status text labels and diagnostic banners.
- `npm run build` passed again after the palette pass: 2410 modules transformed, built in 6.42s. HTTP checks for `http://127.0.0.1:5177/compare` and `http://127.0.0.1:8000/healthz` returned 200/ok.

- Follow-up cool-neutral refinement replaced the remaining warm/dirty grays with #f3f4f6, #e5e7eb, #d1d5db, #9ca3af, and #111827 across theme tokens, CSS hard-coded grays, charts, and heatmaps.
- Restarted the Vite dev server on http://127.0.0.1:5177/ so Tailwind config changes take effect in preview; browser computed styles now show body/sidebar gb(243, 244, 246), header/panels white, borders gb(209, 213, 219), table heads gb(229, 231, 235), and positive status text still green gb(21, 128, 61).
- 
pm run build passed after the cool-neutral refinement: 2410 modules transformed, built in 8.10s. git diff --check passed with only existing CRLF normalization warnings.
- Restored the Dashboard activity heatmap value scale to its original red palette (#fee2e2, #fca5a5, #ef4444, #991b1b) while keeping empty cells on the cool-neutral background. Browser computed styles confirmed the legend and active cells are red again; 
pm run build passed in 4.99s.
- Updated all shared table headers to a gray-black background with white text, including sortable header buttons/icons and markdown table headers. 
pm run build passed in 6.40s; git diff --check passed with only CRLF normalization warnings; the Vite CSS response at http://127.0.0.1:5177/src/main.css contains the new #1f2937 / white table header rules.
- Updated the Research detail page to a single-column card flow: removed the Research Best Candidate card, placed Branches before Recent Runs, and kept Compare Sets after Recent Runs. 
pm run build passed in 4.70s; local source checks confirmed the research two-column grid and ResearchChampionPanel are gone.
- Fixed the Research detail preview blank page after the layout edit by restoring the accidentally removed ResearchTimelinePanel and ResearchEditPanel definitions while keeping the Research Best Candidate card removed. Browser verification now shows the research page rendered with headings 研究分支, 最近 Run, 对比集 and no console errors; 
pm run build passed in 5.00s.
- Updated Compare detail layout so the main result cards are single-column instead of two-column: primary series, drawdown, metric table, Pareto scatter, config diff, and artifact comparison now stack vertically. Browser verification on http://127.0.0.1:5177/compare/cmp_mpcmwcgm_894d454724 confirmed the main panels share the same x/width and render top-to-bottom with no console errors; 
pm run build passed in 4.92s.
- Updated the top search Ctrl K shortcut hint to plain muted text with no border, background, or padding. Browser computed style confirmed transparent background, 0px border width, 0px padding, and muted gray text; 
pm run build passed in 7.27s.
- Moved the Compare metric matrix error from its own full-width row into the card title row next to 关键指标表 via a PanelHeader title metadata slot. Browser DOM verification confirmed the error is inside the header, the separate error row count is 0, and 
pm run build passed in 4.84s.
- Renamed Compare detail chart card titles from 主曲线重叠 to 曲线对比 and from 回撤重叠 to 回撤对比. Browser verification confirmed the new headings are present, the old headings are absent, and no console errors; 
pm run build passed in 5.00s.
- Unified user-facing empty-state copy for compare/run artifact panels by routing remaining `No ...` strings through i18n and adding missing zh-CN mappings for drawdown series, events, notes, snapshots, saved views, saved compare sets, sweeps, and related empty pages. Browser verification on http://127.0.0.1:5177/compare/cmp_mpcmwcgm_894d454724 confirmed `No Drawdown Series Available` / `No Series Data Available` are absent from visible text and Chinese empty states are shown; console errors were empty; npm run build passed in 4.75s.
## status
active

## reason
- Experiment remains active for review; changes are ready for visual inspection in the worktree dev server.
