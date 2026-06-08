---
designSystem:
  name: "Blackbox WebUI"
  version: "2026-06"
  purpose: "A quiet, dense, data-first workspace for quantitative research runs, results, and comparisons."
  audience:
    - "quant researchers"
    - "strategy engineers"
    - "AI agents uploading and inspecting experiment results"
  principles:
    - "Run is the atomic unit; Project, Research, and Branch exist to organize and compare Runs."
    - "Tables, curves, diagnostics, and diffs are the primary UI surfaces."
    - "Prefer operational clarity over decoration."
    - "Every result must be traceable to its context, quality status, and artifacts."
  tokens:
    color:
      ink: "#202326"
      muted: "#60666c"
      subtle: "#858a8f"
      canvas: "#f6f6f2"
      panel: "#fbfbf8"
      panel2: "#edeeea"
      line: "#e1e2dd"
      lineStrong: "#cfd1cc"
      charcoal: "#1c1f22"
      positive: "#16a34a"
      positiveSoft: "#dcfce7"
      negative: "#ef233c"
      negativeSoft: "#fee2e2"
      warning: "#f97316"
      warningSoft: "#fef3c7"
      info: "#0f70ff"
      infoSoft: "#dbeafe"
      tableHeader: "#f3f4f1"
    typography:
      fontFamily:
        - "Noto Sans SC"
        - "Microsoft YaHei"
        - "PingFang SC"
        - "Hiragino Sans GB"
        - "Source Han Sans SC"
        - "Noto Sans CJK SC"
        - "Noto Sans"
        - "ui-sans-serif"
        - "system-ui"
        - "sans-serif"
      body: "14px / 20px"
      tableHeader: "12px / 16px, 600 weight, uppercase where labels are English"
      metricValue: "semibold, tabular numbers"
      letterSpacing: "0"
    shape:
      panelRadius: "8px"
      controlRadius: "6px"
      cardRadiusMax: "8px"
    spacing:
      pagePadding: "24px desktop, 16px mobile"
      panelPadding: "20px"
      tableCellPadding: "12px 16px"
      toolbarGap: "8px"
    elevation:
      default: "flat panels with 1px borders"
      bento: "0 16px 40px rgba(28,31,34,0.08), only when depth is useful"
    components:
      panel: "rounded 8px, border line, panel background, no nested card stacks"
      table: "single-line headers, left aligned by default, horizontal scroll for wide data"
      buttonPrimary: "charcoal background, white text, 36px height"
      buttonSecondary: "white translucent background, line border, 36px height"
      iconButton: "36px square, lucide icon, border transparent by default"
      formControl: "white 80% background, line border, 14px text"
      searchEntry: "top-right search button, 180px wide, opens centered Ctrl+K modal"
      diagnostics: "hidden when clean; red/yellow collapsible card when issues exist"
      chart: "ECharts; lines for series, red area for drawdown, explicit empty states"
  technology:
    framework: "React 18"
    build: "Vite 6"
    styling: "Tailwind CSS 3 plus src/main.css component utilities"
    charts: "ECharts 5 via echarts-for-react"
    icons: "lucide-react"
    markdown: "react-markdown plus remark-gfm"
    fonts: "local Noto Sans SC assets under webui/public/fonts, with system fallbacks"
---

# Blackbox Frontend Design Language

This document is the source of truth for Blackbox WebUI presentation work. It is written for both engineers and coding agents. When UI code and this document diverge, update one of them in the same change.

Blackbox is not a marketing site. It is a quantitative research workstation. The user comes here to answer concrete questions:

- What has run recently?
- Which experiment is best, and why?
- Is this result valid?
- What changed between two or more Runs?
- Which artifact, metric, curve, or config explains the difference?

The interface should therefore feel dense, calm, and inspectable. Avoid decorative layouts that hide data. Prefer tables, curves, diagnostic cards, and diff panels.

## Product Model

The hierarchy is:

`Project -> Research -> Branch -> Run`

`Run` is the smallest execution unit and the source of truth for results. The upper levels aggregate and explain Runs:

- `Project`: groups related research work and provides cross-research comparison.
- `Research`: represents one research question or strategy thesis.
- `Branch`: represents one direction, hypothesis variant, or implementation line.
- `Run`: records one execution, including summary metrics, series, artifacts, diagnostics, context, and notes.

Do not design Run Detail as a miscellaneous artifact dump. It must be a structured result surface.

## Technology Stack

Use the existing frontend stack unless there is a strong local reason to change it:

- React 18 with function components and hooks.
- Vite for dev/build/preview.
- Tailwind CSS for tokens and utility styling.
- `src/main.css` for shared component utilities such as panels, buttons, controls, tables, and markdown rendering.
- ECharts through `echarts-for-react` for all financial and diagnostic charts.
- `lucide-react` for icons in buttons, nav, diagnostics, and actions.
- `react-markdown` with `remark-gfm` for reports and notes.
- Local `Noto Sans SC` web fonts from `webui/public/fonts`, followed by Chinese and system fallbacks.

Do not introduce a component framework, CSS-in-JS system, chart library, or router replacement without updating this document and explaining why the existing stack cannot handle the job.

## Visual Tone

The desired feel is:

- operational
- research-grade
- quiet
- table-heavy
- fast to scan
- explicit about quality issues

The undesired feel is:

- landing page
- decorative dashboard
- card wall
- one-hue theme
- oversized hero typography
- badges and bubbles that do not carry information

Use restrained backgrounds and borders. Use saturated red, green, orange, and blue for semantic text and diagnostic state, not for decorative chart repainting.

## Color System

Use the Tailwind tokens from `webui/tailwind.config.js`:

- `canvas #f6f6f2`: app background.
- `panel #fbfbf8`: primary panel background.
- `panel2 #edeeea`: subtle secondary surface.
- `ink #202326`: primary text.
- `muted #60666c`: labels and secondary text.
- `subtle #858a8f`: tertiary text.
- `line #e1e2dd`: default divider and border.
- `lineStrong #cfd1cc`: focused border or stronger divider.
- `charcoal #1c1f22`: primary button background.

Semantic colors:

- `positive #16a34a`: success, positive deltas, completed status text.
- `negative #ef233c`: errors, failed status text, severe diagnostics.
- `warning #f97316`: warnings and degraded quality.
- `info #0f70ff`: selected informational state.

Soft semantic backgrounds:

- `positiveSoft #dcfce7`
- `negativeSoft #fee2e2`
- `warningSoft #fef3c7`
- `infoSoft #dbeafe`

Chart palettes may use different ECharts colors when the chart needs contrast or continuity. Do not globally change chart palettes just because semantic text needs stronger color.

## Typography

Primary font stack:

`Noto Sans SC`, `Microsoft YaHei`, `PingFang SC`, `Hiragino Sans GB`, `Source Han Sans SC`, `Noto Sans CJK SC`, `Noto Sans`, `ui-sans-serif`, `system-ui`, `sans-serif`

Rules:

- Body text defaults to Tailwind `text-sm`.
- Table headers are `12px / 16px`, semibold, and must stay on one line.
- Metric values use `tabular-nums` and semibold weight.
- Do not use negative letter spacing.
- Do not scale font size with viewport width.
- Keep headings compact inside panels; reserve large type for true page headers only.

## Layout

The default application layout is a persistent navigation shell plus a page content region. URL state must identify the current page and selected entity so browser refresh does not return to the dashboard.

Page sections should be full-width bands or normal constrained layouts. Cards are for repeated items, modals, and framed tools. Avoid cards inside cards.

Use horizontal scrolling for wide analytical tables. Do not solve wide data by wrapping header labels into multiple lines.

Preferred spacing:

- Page padding: `24px` on desktop, `16px` on mobile.
- Panel padding: `20px`.
- Table cell padding: `12px 16px`.
- Toolbar gap: `8px`.

## Core Components

### Panels

Panels use:

- `rounded-bento`
- `border border-line`
- `bg-panel`
- no default heavy shadow

Panel headers should contain concise titles and real actions only. Do not add decorative badges to the top-right of cards unless the badge changes user behavior or communicates state.

Collapsible panel buttons:

- use a lucide chevron icon
- no visible border
- clear hover state
- stable square hit target

### Buttons

Use existing utility classes:

- `.primary-button` for the main page or modal action.
- `.secondary-button` for normal commands.
- `.icon-button` for icon-only actions.

Use lucide icons when an icon exists. Avoid manually drawn SVG icons for ordinary actions.

### Inputs

Use `.form-control` for text inputs, selects, and textareas. Read-only display fields should look like single-line controls when the value is short. Editing areas should be read-only by default unless the user clicks an edit icon.

Top-right global search:

- label: `搜索`
- width: `180px`
- opens a centered command palette with `Ctrl+K` or `Cmd+K`
- no bottom instruction bar
- input should be compact, not a large hero search box

### Tables

Tables are the default way to browse entities and result data.

Required table rules:

- Header row is one line only.
- Header font is 12px semibold.
- Header text is left aligned by default.
- Numeric columns align right.
- Header labels do not wrap; wide tables scroll horizontally.
- Default sorting for entity tables should prioritize modified time, updated time, or last run time.
- Data tables should support sorting on all columns unless the table is intentionally static.
- If a data table includes date-like columns such as `DATE`, `DATETIME`, `TRADE_DATE`, `END_DATE`, or `TIME`, put those columns first.

Use `.table-head` for `<thead>` and `.table-cell` for normal body cells.

### Status And Diagnostics

Quality diagnostics are hidden when clean. If there are issues, show a top-of-page card:

- red for blocking errors
- orange/yellow for warnings
- collapsible details
- concrete reason and remediation where possible

Do not bury result quality issues in a tab. A Run with invalid or incomplete results must be visibly suspect before the user reads the metrics.

### Charts

Use ECharts for charts.

Financial result chart rules:

- Strategy NAV/return/pnl views should show the main cumulative series and drawdown together.
- Drawdown uses red filled area.
- If no series data exists, show `No Series Data Available`.
- Do not render misleading partial preview data as a full curve.
- Series mode must be explicit where needed: `nav`, `return`, `pnl`, or future modes.

Do not use chart colors as the main carrier for status meaning. Pair color with labels and table values.

### Modals

Use modals for focused create/edit/view flows:

- global command search
- create Project/Research/Branch/Run/Compare Set
- result artifact preview
- metric table/plot detail

Keep modal contents dense. Avoid explanatory footers unless they change the user's next action.

## Page Patterns

### Dashboard

Dashboard should answer what changed recently. It should show:

- compact metrics in a single row where possible
- recent Runs
- recent activity
- saved or active Compare work
- clear entry points into Projects, Researches, Branches, Runs, and Compare

Avoid spreading many Create buttons throughout the page. Use the navigation-level create menu.

### Runs Board

The global Runs board is a P0 surface. It must support:

- browse all Runs
- filter
- search
- sort
- quick navigation to Run Detail

Columns should stay stable and scan-friendly. Prefer Branch, Run, Status, Creator, Sharpe, Runtime, Updated for recent-run tables.

### Run Detail

Run Detail is the primary result surface. It should be structured in this order:

1. Run identity and context.
2. Quality diagnostics, only if issues exist.
3. Primary result view template.
4. Key metrics.
5. Result groups and artifacts.
6. Context: code, data, environment, config, notes.

Result views must be role-aware:

- image roles render as images.
- table roles render as sortable tables.
- single or multiple series roles support both table and plot views.
- scalar metrics render as compact metric cards or metric tables.

Use `Context` as the label for Code/Data/Env style provenance.

### Compare

Compare should match the actual quant workflow:

- choose comparable entities or a saved Compare Set
- see curve overlay first when the question is performance path
- see key metric table next
- see diagnostics and config differences to explain why

Quick Compare cards at Project, Research, and Branch levels should only support:

- NAV/return/pnl series overlay
- key metric table

Single Run pages do not need Quick Compare.

### Result Data View

Artifact View Data should render by result role:

- PNG/JPEG/SVG image: image preview.
- Table: sortable table.
- Series: table plus plot.
- Multiple series: table plus plot with selectable series when necessary.

Date/time columns move to the front. All visible columns are sortable by default.

## Copywriting

Use short operational labels. Prefer:

- `Runs`
- `Compare`
- `Context`
- `Diagnostics`
- `View Data`
- `No Series Data Available`

Avoid visible in-app text that explains how the UI is styled or describes basic usage. The interface should expose controls directly rather than explaining itself.

Chinese UI text is allowed and preferred where the active product language is Chinese. Keep domain names, strategy names, and run names as uploaded.

## Accessibility And Responsiveness

Minimum requirements:

- All buttons have accessible names.
- Icon-only buttons need a title or aria-label.
- Keyboard search opens with `Ctrl+K` and `Cmd+K`.
- Modals close with `Esc`.
- Text must not overlap on mobile or desktop.
- Fixed-format UI elements need stable dimensions.
- Wide tables scroll horizontally rather than compressing into unreadable wrapping.

## Implementation Rules For Agents

When implementing frontend changes:

1. Read nearby code before editing.
2. Reuse existing component utilities and Tailwind tokens.
3. Prefer small scoped edits over broad rewrites.
4. Keep tables, charts, and diagnostics aligned with this document.
5. Use lucide icons for standard actions.
6. Verify with `npm run build`.
7. For visual changes, verify in the browser against the relevant localhost route.
8. Do not change chart palettes, semantic colors, or layout density casually.
9. Do not remove necessary decorative icons when they help recognition.
10. Update this file when a design decision becomes a new rule.

## Do

- Make dense data easy to scan.
- Keep Run result surfaces structured by role.
- Show quality problems before metrics.
- Use sortable tables by default.
- Use route-aware pages.
- Keep controls compact.
- Use semantic color for status and diagnostics.
- Preserve local Noto Sans SC font loading.

## Do Not

- Build a landing page for the product shell.
- Add ornamental badges, bubbles, or nested cards.
- Let table headers wrap.
- Hide important diagnostics in secondary tabs.
- Render preview-only series as full result curves.
- Use broad gradients, blobs, or decorative backgrounds.
- Introduce another UI framework without a documented reason.
- Change uploaded domain names, run names, or strategy names for aesthetics.
