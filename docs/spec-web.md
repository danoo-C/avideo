# avideo — Specification (web app)

This file specifies the local web app started with `avideo serve`: launch, architecture, visual design, screens, viewer, settings panel, live updates, export/import, shortcuts, API, performance, states, accessibility and security.

- Every analysis parameter is defined in [spec.md](spec.md). This file maps controls to those parameter keys and never redefines them.
- The visual reference is the **Web app** row of the drafts canvas (*avideo UI drafts*). Where the drafts and this spec differ, this spec wins.

---

## 1. Principles

1. **Clean.** One accent color, quiet surfaces, content first. The video and its analysis are the brightest things on screen.
2. **Fast.** Display changes are instant (client-side). Analysis changes show a result within a fraction of a second while paused, and stream live while running. No page reloads.
3. **Easy.** Sensible defaults, settings grouped in pipeline order, a plain-language explanation on every control, undo for everything.
4. **See what is happening.** Every pipeline stage can be viewed live. Original and result can be compared side by side, blended or wiped.
5. **Local.** Runs on `127.0.0.1`, reads videos straight from disk, makes no external requests and works offline.
6. **One engine.** The web app only calls the core (spec.md). Results are identical to the CLI, and exported settings run unchanged with `avideo … --config`.

---

## 2. Launch — `avideo serve`

```
avideo serve [PATH] [options]
```

`PATH` (optional) decides what opens:

| PATH | Opens |
|---|---|
| none | The Open screen on the current folder |
| folder | The Open screen on that folder |
| video file | That video in the workspace (last used tool, or Heatmap) |
| output folder (contains `*_run.json`) | Its video with all results found in the folder loaded |
| `.avideo` session | The session |

| Option | Default | Effect |
|---|---|---|
| `--port N` | `8765` | If busy, the next free port up to +20 is used and printed |
| `--host ADDR` | `127.0.0.1` | Non-loopback addresses require `--allow-remote` |
| `--allow-remote` | off | Allows binding to other addresses. Prints a red warning. The token is still required. |
| `--root DIR` | the folder of PATH, or the current folder | Files can be browsed and read only inside this folder |
| `-o, --out DIR` | `<root>/avideo-out` | Output root (`output.dir`) |
| `--open` / `--no-open` | `--open` | Open the default browser at start |
| `-v` | | Verbose request log |

The terminal side (banner, request log, key hints) is specified in [spec-cli.md](spec-cli.md) §6.8. The server runs until ctrl+c or `q`. Running jobs are then cancelled and write partial results, as in spec.md §13.3.

---

## 3. Architecture

### 3.1 Server

- **FastAPI** app served by **uvicorn**, single process. Analysis runs in a **process pool** through the core runner (spec.md §3.3), so the server stays responsive.
- **Workspace:** one opened video plus, per tool, its settings, latest preview result and latest full result. Workspaces live in memory. Several browser tabs may share one workspace; changes are broadcast to all of them.
- **Jobs** per workspace: at most one **preview run** (the visible tool) and one **full run** at a time. A second full run request is queued. Full runs keep going when the user switches tools; progress shows next to the tool in the sidebar.
- **Persistence** (data folder: Linux `~/.local/share/avideo`, macOS `~/Library/Application Support/avideo`, Windows `%APPDATA%\avideo`):

| What | Where |
|---|---|
| Recent videos (max 20) | `recent.json` |
| Preferences | `preferences.toml` |
| Last settings per video (keyed by quick hash) | `video-settings/<hash>.toml` |
| User presets | config folder `presets/` (shared with the CLI) |
| Result cache | cache folder (spec.md §12.4) |

UI-only state (collapsed sections, last tool, panel widths) is kept in the browser's `localStorage`. All access is wrapped so the app works when storage is unavailable.

### 3.2 Frontend

- Static files bundled in the package (`avideo/web/static/`). **No build step, no framework, no CDN.** Plain ES modules plus vendored fonts (Inter, JetBrains Mono as `woff2`).
- Module layout:
  ```
  index.html
  app.js              # bootstrap, routing (open / workspace), global shortcuts
  store.js            # state, undo/redo history, subscriptions
  api.js              # REST + WebSocket client, binary framing, reconnect
  schema.js           # parameter schema from /api/schema → labels, ranges, help
  viewer/             # WebGL2 viewer: layers, colormap LUTs, blend/wipe, zoom/pan, overlays, ROI drawing
  components/         # segmented, slider-row, select, number, time-field, swatches, tile, panel, dialog, toast, tooltip, palette
  tools/<tool>.js     # one per tool: settings panel layout, stages, tool-specific views and charts
  charts/             # small canvas chart helpers (area, line, bars, polar)
  styles/tokens.css   # design tokens (section 4)
  styles/app.css
  ```
- **Generated settings panels.** Each `tools/<tool>.js` declares its panel: sections, rows, control types, which key each control edits and when it is visible. Labels, ranges, defaults and help texts come from `/api/schema`, which the server builds from the core pydantic models. Wording therefore matches the CLI help exactly.
- **Viewer:** WebGL2. Colormapping, normalization, blend and wipe happen in a fragment shader, so display changes cost one frame. Canvas 2D is the fallback when WebGL2 is unavailable (slower, same features).

---

## 4. Visual design

### 4.1 Color tokens

The **dark theme is the default.** Light follows the system when the preference is "System", or is chosen explicitly. The viewer background is always black in both themes, so video and heatmaps look the same.

| Token | Dark | Light | Used for |
|---|---|---|---|
| `--bg` | `#0E0F12` | `#F6F7F9` | Page background |
| `--surface` | `#111317` | `#FFFFFF` | Top bar, sidebars, settings panel |
| `--panel` | `#13151A` | `#FFFFFF` | Cards, tiles, transport, dialogs |
| `--raised` | `#1A1D23` | `#F1F3F6` | Inputs, secondary buttons |
| `--control` | `#16191E` | `#EEF0F3` | Segmented control track |
| `--selected` | `#2B303A` | `#FFFFFF` (with shadow) | Selected segment |
| `--hover` | `#1F232B` | `#E9ECF0` | Hover / active nav item |
| `--border` | `#23262E` | `#E2E5EA` | Dividers, card borders |
| `--border-strong` | `#2A2E37` | `#D3D7DE` | Inputs, buttons |
| `--text` | `#E8EAEE` | `#15171C` | Primary text |
| `--text-muted` | `#A0A7B4` | `#545B68` | Secondary text, unselected segments |
| `--text-label` | `#8F96A3` | `#5F6774` | Small labels, captions |
| `--accent` | `#F5A524` | `#F5A524` | Primary button, slider fill, played timeline, focus ring, active icon |
| `--accent-text` | `#F5A524` | `#9A5B00` | Accent used as text or links |
| `--on-accent` | `#1A1305` | `#1A1305` | Text on accent backgrounds |
| `--success` | `#3DD68C` | `#14834F` | Live dot, done states |
| `--warning` | `#F0B429` | `#8A5A00` | Warnings (always with an icon) |
| `--danger` | `#F26D6D` | `#C42B2B` | Errors, destructive actions |
| `--viewer` | `#000000` | `#000000` | Viewer background |
| `--overlay-chip` | `rgba(10,11,14,0.75)` | same | Chips and legends over video |

All text/background pairs meet WCAG AA (4.5:1 for text under 24 px). Heatmap colors come from the selected colormap (spec.md §6.2.6); the UI never uses the colormap colors elsewhere, except in the logo mark.

### 4.2 Typography

- **Inter** for UI and **JetBrains Mono** for numbers, timecodes, paths, file sizes and code. Both are bundled.
- Base size 14 px.
- Scale:

| Size | Use |
|---|---|
| 11 px | Uppercase group labels (`letter-spacing: 0.08em`) and chips |
| 12 px | Labels and captions |
| 13 px | Controls |
| 14 px | Body |
| 15 px | Panel titles |
| 18 px | Section titles |
| 22 px | Stat values |
| 26 px | Page titles |

- Weights: 400, 500 (controls), 600 (titles, primary button) and 700 (wordmark, page titles).
- Tabular numerals for all changing numbers.

### 4.3 Spacing, shape, elevation

- **Spacing:** 4 px grid; panel padding 16 px; section gap 14 px; row gap 10–12 px.
- **Radii:**

| Radius | Use |
|---|---|
| 6 px | Segments inside tracks |
| 7–8 px | Buttons, inputs, nav items |
| 9–10 px | Tracks, cards, tiles, transport |
| 12 px | Viewer |
| 14 px | Dialogs |
| full | Chips, play button |

- **Heights:**

| Height | Use |
|---|---|
| 28–30 px | Segments |
| 34–36 px | Inputs and buttons |
| 38 px | Play button |
| 44 px | Primary action |

- **Elevation:** none in the dark theme (borders only). Dialogs and popovers get a soft shadow in both themes.

### 4.4 Iconography and motion

- **Icons:** inline SVG, 24 px grid, 1.7 px stroke, round caps. Shown at 16–18 px; filled glyphs only for play/pause. Every icon-only button has an `aria-label` and a tooltip.
- **Logo:** a 3×3 grid of rounded squares in inferno colors, next to the bold wordmark `avideo`.
- **Motion:** 120–160 ms ease-out for hover, press and expand. Data updates are never animated (no tweening of numbers or images). The only continuous animations are the LIVE dot and the progress bars. Everything respects `prefers-reduced-motion`.

### 4.5 Components

| Component | Spec |
|---|---|
| Segmented control | Track (`--control`, 1 px border, radius 9–10) with buttons; selected = `--selected` background and `--text`; `aria-pressed`. Wraps on narrow widths. |
| Slider row | Label · native range input (accent fill) · monospace value (editable on click). Double-click the label to reset to default. |
| Channel slider row | Same, with a colored dot and channel letter (R/G/B, H/S/V, L/a/b, r/g/b, Y). |
| Range slider | Two-handle slider for color ranges, with the selected color band drawn in its track. |
| Select | Native `<select>` styled like inputs. |
| Number / time field | Monospace input with validation; time fields accept every Time syntax (spec.md §4) and offer "use current frame". |
| Swatch grid | Colormap buttons showing their gradient and name; selected = 2 px accent ring. |
| Section | `<details>` with a summary row (title left, current-state summary right in `--text-label`). Remembers open/closed. A dot before the title marks "changed from preset". |
| Stat tile | Small label, 22 px monospace value, caption; optional thin progress bar. |
| Chip | Pill over video with `--overlay-chip` background. |
| Toast | Bottom-right, auto-dismiss after 5 s, with an optional action (Undo, Reveal, Details). |
| Dialog | Centered, radius 14, max width 760 px, focus-trapped, closes with Esc. |

---

## 5. Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│ top bar: logo · file name + meta ·············· Open  Import  Export  ☀  ? │
├──────────┬──────────────────────────────────────────────┬──────────────────┤
│ tools    │ stage selector            view mode selector │ settings panel   │
│ Analyze  │ ┌──────────────────────────────────────────┐ │ (tool-specific)  │
│ Extract  │ │                 viewer                   │ │                  │
│ Output   │ └──────────────────────────────────────────┘ │                  │
│          │ blend / wipe slider (when active)            │                  │
│          │ transport + activity scrubber                │                  │
│          │ pixel inspector line                         │ quality · Run    │
│ status   │ stat tiles / tool charts                     │ CLI command box  │
└──────────┴──────────────────────────────────────────────┴──────────────────┘
```

- **Top bar:** logo; current file name with monospace meta (`1920×1080 · 29.97 fps · 04:12.2 · H.264`); Open, Import and Export buttons; theme toggle; help (`?` shortcuts overlay).
- **Tools sidebar:**
  - groups **Analyze** (Heatmap, Timeline, Scenes, Optical flow, Flicker, Compare), **Extract** (Background, Pixel stats, Barcode, Contact sheet) and **Output** (Report, Video info)
  - each item shows an icon; small status marks on the right: a progress ring while a full run is going, ✓ when a full result exists, a dot when the full result is outdated
  - bottom: local status chip (`● Local only · 127.0.0.1:8765`)
- **Viewer column** and **settings panel** as in the drafts.

**Responsive behavior:**

| Width | Layout |
|---|---|
| ≥ 1280 px | Three columns: sidebar 200–220 px, viewer flexible, settings 300–340 px |
| 960–1279 px | Sidebar collapses to icons (labels in tooltips); settings 280 px |
| 720–959 px | Settings panel becomes a drawer opened from a "Settings" button on the viewer toolbar |
| < 720 px (phone) | Single column: tools in a top menu, then viewer, transport, settings. All features remain available; dense controls keep 36 px touch height. |

---

## 6. Screens

### 6.1 Open a video

- **Page:** title "Open a video", subtitle "Videos are read straight from disk. Nothing is uploaded or leaves this machine."
- **File browser card** (main column):
  - breadcrumb path (clickable segments) and a filter field
  - list columns: icon, name, length, size; folders first, then videos (other files hidden; settings, session and output folders shown with their own icons)
  - lengths are loaded lazily per row
  - **interaction:** single click selects; double click or Enter opens (folder: navigate; video: open in workspace; output folder: open with results; session: open session)
  - footer: selection summary, "Import session…" and primary **Open in Heatmap**. The button label names the last used tool.
- **Side column:**
  - **Drop zone:** "Drop a video here, or a settings .toml, a saved .npy heatmap or an .avideo session." The browser cannot give a dropped file's path, so dropped videos are copied into avideo's cache (`uploads/`) and the app says so. The file browser is the recommended way.
  - **Recent:** up to 6 items with thumbnail, name and "Tool · when". "Show all" opens the full list (max 20) with remove buttons.

### 6.2 Workspace (common to all tools)

- The viewer, transport, stage selector and view modes work the same in every tool (section 7).
- Switching tools keeps the video, playhead, zoom and view mode. Each tool remembers its own settings per video.
- Opening a tool auto-starts a **preview run** (preference "Auto-run preview", default on) and shows its result live.
- The **settings panel** has:
  - a header (tool name, "changes apply live")
  - preset row
  - the tool's sections
  - footer: quality toggle (`Preview · 25%` | `Full quality`), primary **Run full analysis** (becomes **Stop** while a full run is going), and the CLI command box
- **Result status badge** in the viewer toolbar: `Preview`, `Full ✓`, `Full · outdated`, or `Partial · stopped at 45%`.

### 6.3 Tool pages

Each entry lists the stages (stage selector), the extra views, and the main content below the transport.

#### Heatmap

- **Stages:** Original · Preprocessed · Thresholded (only when thresholding is on) · Change mask · Heatmap · Channels (only for `combine = separate`).
- **Below the transport — stat tiles:**
  - Progress (percent, fps, ETA, bar)
  - Changed this frame (percent of ROI pixels)
  - Hottest pixel (count, location; clicking zooms to it)
  - Never changed (percent)
  - after a run: Busiest frame (click to seek) and Noise σ / delta used
- **Overlays:** colorbar legend (bottom right) with normalization label and min/mid/max; LIVE chip (bottom left) while running.
- **After a run:** scrubbing shows the heatmap **as it was at that frame**, using the stored snapshots (nearest earlier snapshot). The "Final" toggle in the legend pins the final heatmap regardless of playhead.

#### Timeline

- **Stages:** Original · Change mask.
- **Main content:** a full-width chart under the transport:
  - area of percent changed (accent), line of mean luma (muted, right axis), active segments shaded, peaks as markers
  - hover shows time and values; click seeks; drag selects a range with the actions "Set as analysis range" (sets `input.start`/`input.end`) and "Zoom"
- **Lists:** peaks (time, value) and segments (start, end, length); clicking seeks.

#### Scenes

- **Stages:** Original · Difference.
- **Scene strip:** horizontal, scrollable cards with thumbnail, index, start time, duration and a type badge (`scene`, `frozen` warning-colored, `black` dark). Clicking seeks; the current scene is highlighted.
- **Toggles:** table view (all columns of `scenes.csv`); markers for cuts on the scrubber.

#### Optical flow

- **Stages:** Original · Flow (current frame) · Magnitude · Direction · Arrows.
- **Legends:** color-wheel legend for Flow/Direction; magnitude colorbar.
- **Tiles:** mean speed, dominant direction (with an arrow), percent moving; a small direction rose chart.

#### Flicker

- **Stages:** Original · Frequency · Amplitude.
- **Legend:** in Hz, with the aliasing note when `max_hz` = Nyquist.
- **Pixel peaks:** clicking a pixel shows its three strongest peaks (from `flicker_peaks`) in a small bar chart next to the average spectrum chart.
- Window progress is shown while the first window fills.

#### Compare

- A **Video B** picker sits at the top of the settings panel (opens the file browser in a dialog).
- **Stages:** A · B · Difference · Difference heatmap. The view modes compare **A and B** (side by side, blend A↔B, wipe A|B), or Original vs the selected processed stage when a difference stage is chosen.
- **Charts:** PSNR and SSIM per frame (toggle MAD), with worst-frame markers.
- **Worst frames list:** thumbnails of A|B with metrics; click seeks.
- **Alignment:** with `align = auto`, the found offset is shown with a "use" action that writes it into `compare.offset`.

#### Background

- **Stages:** Original · Background · Foreground.
- **Action:** "Use current frame as foreground frame" sets `background.foreground_frame`.

#### Pixel stats

- **Stages:** Original · one entry per selected measure (Mean, Std, Min, Max, Range).
- **Markers:** an overlay toggle shows stuck, dead and hot pixels as rings.
- **Table:** x, y, kind, mean, std; clicking zooms the viewer to that pixel at 800%.

#### Barcode

- The main content shows the barcode at full width and large height.
- Hover shows the time and a thumbnail popover; click seeks the viewer, which is reduced to a smaller size on this page.

#### Contact sheet

- The main content shows the generated sheet, zoomable.
- Changing layout settings regenerates it quickly, since only cols × rows frames are decoded.

#### Report

- **Checklist** of tools to include (`report.tools`), each showing whether a full result exists ("ready") or will be computed ("will run"); title field.
- **Generate report:** runs the missing tools in one pass with progress per tool.
- **Result:** shown in a sandboxed `<iframe>` preview, with actions Open in new tab and Reveal file.

#### Video info

- Metadata panel (same fields as the CLI `info`, spec.md §6.1) as a two-column grid.
- Checks with ✓, and warnings with explanation, tip and an **Apply** button where a setting fixes it:

| Warning | Apply sets |
|---|---|
| W005 | `input.deinterlace = on` |
| W004 | `heatmap.change.delta = auto` and `heatmap.preprocess.blur = 1` |
| W003 | `heatmap.preprocess.blur = 1` |
| W002 | Toggles `input.rotate` between `auto` and `0` |

### 6.4 Export & import dialog

Opened from the top bar (Export: Ctrl/Cmd+E, Import: Ctrl/Cmd+I). Two tabs: **Export** and **Import**. The header shows the file and tool; the close button is on the right.

**Export tab:**

- **Scope:** "This tool" (default) or "All tools with results".
- **Item list** (checkbox rows) built from the tool's outputs (spec.md §6, "Outputs"), plus **Settings (TOML)** and **Session (.avideo)** always. Each row shows a name, format pill, one-line description and estimated size.
- Rows with options expand when checked:

| Item | Options |
|---|---|
| Heatmap image | Colormap and normalization (prefilled from the current display), colorbar, image size |
| Overlay | Base, opacity, mode |
| Time-lapse | Snapshots, fps, scale |
| Rolling | Window, mode |

  These edit the `heatmap.output.*` keys.
- **Destination:** folder field, prefilled with `<out>/<stem>/`, plus Browse… (server-side folder picker limited to allowed write locations; section 16).
- **Footer:** "N files · about X MB", Cancel, and primary **Export N files**.
- **Quality:** export always uses the **full-quality** result. If only a preview result exists, the button reads **Run full analysis & export**: the full run starts and the export happens when it finishes, with progress in the dialog.
- **When done:** a toast "Exported 4 files" with **Reveal in file manager**.

**Import tab:**

- Drop zone and "choose a file" link. Types are recognized automatically:

| File | Effect |
|---|---|
| `.toml` / `.json` settings | Applied to the tools whose sections it contains. Toast: "Applied 6 settings to Heatmap" with **Undo**. Unknown keys are listed in a warning; the rest is applied. |
| PNG written by avideo | Its embedded settings are applied as above |
| `.npy` heatmap counts | Loaded as the Heatmap result if its size matches the video's processing size (otherwise the result is shown at its own size with a note). With no video open, a **result-only workspace** opens (no Original stage). |
| `.avideo` session | Opens the session. If the video moved, a locate dialog asks for it (quick hash verified). |

- Three cards explain the types, and a short TOML sample shows what a settings file looks like.

### 6.5 Preferences

Dialog opened from the command palette or the `?` menu.

| Preference | Default |
|---|---|
| Theme: System / Dark / Light | System (dark when the system has no preference) |
| Output folder | `<root>/avideo-out` |
| Preview resolution: 12.5% / 25% / 50% | 25% |
| Live update rate: 5 / 10 / 15 / 30 fps | 12 fps |
| Auto-run preview when opening a tool | on |
| Parallel workers for full runs | auto |
| Cache size limit, with a Clear cache button | 2 GB |
| Default preset for new videos | none |
| Restore last workspace on start | on |
| Show pixel inspector line | on |

### 6.6 Shortcuts overlay

`?` opens a two-column list of all shortcuts (section 11), grouped by Playback, View, Analysis and App.

### 6.7 Command palette

Ctrl/Cmd+K opens a fuzzy search over:

- tools ("Go to Flicker")
- actions (Open, Export, Import, Run full analysis, Stop, Toggle theme, Preferences)
- view modes and stages
- **settings**: typing "delta" focuses the Delta slider, opening its section if needed
- presets
- recent videos

---

## 7. Viewer

### 7.1 Stage selector and view modes

- **Stage selector** (segmented, left): the tool's stages (section 6.3). It picks what the **processed layer** shows.
- **View modes** (segmented, right):

| Mode | Shows |
|---|---|
| **Single** | Only the processed layer |
| **Side by side** | Original (left) and processed (right), each with a label chip; zoom and pan are synced |
| **Blend** | Processed layer over the original with adjustable opacity |
| **Wipe** | Original left of a vertical divider, processed right |

In Compare, "original" and "processed" become A and B unless a difference stage is selected.

### 7.2 Blend

- Slider row under the viewer: `Original` ── slider ── `Processed`, with a tick at the middle.
  - 0 = only original
  - 50 = both at 50%
  - 100 = only processed
- Value label shows `both 50%` at the middle and `NN% processed` otherwise. A **50 / 50** button and double-click on the slider reset to 50.
- Keys: `[` and `]` change by 10; `0` resets.

### 7.3 Wipe

- Dragging anywhere on the viewer moves the divider; the slider row under the viewer does the same. The divider has a round handle with ⟨⟩ arrows.
- Label chips: `Original` top left, stage name top right.
- Orientation toggle: vertical (default) or horizontal.
- Panning in Wipe mode uses Space+drag or the middle mouse button.

### 7.4 Zoom and pan

- Scroll (or pinch) zooms around the cursor, 10%–3200%.
- Drag pans (outside Wipe mode).
- `F` / double-click fits; `Z` = 100%.
- Above 100%, pixels are drawn nearest-neighbor (crisp) so single pixels can be inspected.
- All layers stay aligned in every mode.

### 7.5 Overlays

| Overlay | Position | When |
|---|---|---|
| LIVE chip | bottom left | `● LIVE · preview 25%` / `full quality` while a run streams |
| Colormap legend | bottom right | stages with a colormap; label + min/mid/max (and Hz, px/frame, etc. as relevant) |
| ROI outline | over video | dashed accent outline of the region of interest; excluded area dimmed |
| Label chips | top corners | Side by side and Wipe |
| Warnings banner | top | decode problems, stabilization failures (dismissible) |

### 7.6 Pixel inspector

A one-line strip under the transport, shown on hover. It lists the pixel's source coordinates, then values that depend on the tool. Heatmap example: `x 612 y 488 · RGB 182 64 51 · levels 1 0 0 · count 412 · 5.4% of frames`.

- Other tools show their own values: flow speed and direction, flicker Hz and amplitude, stats mean and std, compare A/B/difference.
- Hidden with `I` or in preferences.

### 7.7 Transport and activity scrubber

- **Play/pause** (accent round button), timecode `MM:SS.f / total`, frame counter `frame N / total`.
- **Scrubber:** per-frame bars of the tool's activity metric (heatmap/timeline: percent changed; flow: mean speed; compare: 1 − SSIM). Played part in accent, the rest in a muted color, unprocessed part empty. Playhead line on top. Click or drag seeks (a transparent native range input covers it for keyboard and screen readers).
- Scene cuts and peaks can be shown as ticks on the scrubber.
- Frame stepping with arrow keys (section 11).

### 7.8 Playback and live following

- **While a run streams:** the viewer **follows live**, showing the frame being processed and its stages. Seeking or pausing turns following off. A **Follow live** button appears to turn it back on.
- **While paused (frame inspector):** the server computes the selected stages for exactly that frame with the current settings. Moving a pipeline slider recomputes them immediately (latest request wins) without restarting the whole run. This is the main way to tune thresholds.
- **After a run:** play replays the video. Stages are computed on the fly at preview size, and accumulated stages (heatmap, magnitude) come from snapshots, as described for Heatmap.

---

## 8. Settings panel

### 8.1 Behavior classes

Every control belongs to one class, which decides what happens when it changes:

| Class | What happens | Keys |
|---|---|---|
| **Display** | Client-side only, next frame (≤ 16 ms); no server call | `heatmap.output.normalize`, `vmax`, `colormap`, `composite_scale`; `flow.colormap`, `flicker.colormap`, `stats.colormap`, `compare.colormap`; view mode, blend, wipe, zoom |
| **Pipeline** | Paused: frame inspector recomputes (≤ 150 ms). Running/preview: the preview run restarts 200 ms after the last change. A full result becomes "outdated". | all detection and algorithm keys (`heatmap.space`, `preprocess.*`, `threshold.*`, `change.*`, `cleanup.*`, other tools' algorithm keys), `input.roi`, `input.stabilize`, `input.normalize_exposure` |
| **Input** | Same as Pipeline, and the scrubber resets | `input.start`, `end`, `step`, `max_frames`, `resize`, `rotate`, `deinterlace`, `backend` |
| **Export** | Stored only; used when exporting | all `*.output.files`, `heatmap.output.image_size`, `colorbar`, `overlay_*`, `timelapse_*`, `rolling_*`, `report.self_contained`, `contact.format` |

### 8.2 Common rows (every tool)

**Preset row:**

- Select with built-in and user presets; an `(edited)` suffix when values differ.
- **Save** (overwrite a user preset) and **Save as…** buttons.
- Choosing a preset is one undoable step.

**Input section** (summary shows `N frames`):

| Control | Key(s) |
|---|---|
| Start / End time fields with "use current frame" buttons; drag on the scrubber with Shift to set the range | `input.start`, `input.end` |
| Every Nth frame (number) | `input.step` |
| Max frames (number, under "More") | `input.max_frames` |
| Resize (select 25/50/75/100%, Custom…) | `input.resize` |
| Region of interest: summary + **Draw…** (rectangle or polygon on the viewer), **Load mask…**, **Clear** | `input.roi` |
| Crop outputs to region (checkbox) | `input.roi_crop` |
| Stabilize (select) | `input.stabilize` |
| Exposure normalization (select) | `input.normalize_exposure` |
| Advanced: Rotation, Deinterlace, Decoder (selects) | `input.rotate`, `input.deinterlace`, `input.backend` |

### 8.3 Heatmap controls

**Color space & preprocess**

| Control | Key |
|---|---|
| Color space (segmented: Gray · RGB · HSV · Lab · rgb·n) | `heatmap.space` |
| Blur (slider 0–10, step 0.1) | `heatmap.preprocess.blur` |

**Pre-threshold** (summary e.g. `RGB · fixed` or `off`)

| Control | Key | Visible when |
|---|---|---|
| "Threshold frames before comparing" (checkbox) | `heatmap.threshold.enabled` | always |
| Method (segmented: Fixed · Otsu · Adaptive · Range) | `heatmap.threshold.method` | enabled |
| Channel slider rows (one per channel, colored dots, 0–255). With Otsu they are disabled and show `auto N`. | `heatmap.threshold.values` | fixed/otsu, 2 levels |
| Levels per channel (segmented: 2 · 3 · 4 · 8 · Custom) | `heatmap.threshold.levels` | fixed/otsu |
| Hysteresis (slider 0–64, shows `±N`) | `heatmap.threshold.hysteresis` | enabled, not range |
| Otsu scope (segmented: Whole video · Each frame) | `heatmap.threshold.otsu_scope` | otsu |
| Block size, Offset (sliders) | `adaptive_block`, `adaptive_offset` | adaptive |
| Per-channel range sliders with color band preview; **Pick color** eyedropper: click the viewer to set a range around that color (default tolerance H ±10, S ±60, V ±60, adjustable) | `range_lower`, `range_upper` | range |
| Invert (checkbox) | `range_invert` | range |

**Change detection** (summary e.g. `vs previous frame`)

| Control | Key | Visible when |
|---|---|---|
| Compare each frame against (select) | `heatmap.change.reference` | always |
| Reference frame (time field + use current frame) | `reference_frame` | reference = frame |
| Background model (segmented), Learning rate (log slider) | `background_model`, `background_rate` | reference = background |
| Distance (segmented: Per channel · Euclidean · ΔE) | `heatmap.change.distance` | threshold off |
| Delta (slider 0–64, type up to 255) + **Auto** toggle showing `auto → 9` | `heatmap.change.delta` | threshold off (otherwise shown disabled: "any level change counts") |
| Combine channels (segmented: Any · All · Majority · Sum · Separate) | `heatmap.change.combine` | more than one channel (otherwise disabled with a note) |

**Cleanup**

| Control | Key |
|---|---|
| Speckle removal (select: Off · 3 · 5 · 7 px · Custom) | `heatmap.cleanup.open` |
| Minimum run, frames (number) | `heatmap.cleanup.min_run` |

**Display** (summary: "instant, no reprocessing")

| Control | Key |
|---|---|
| Normalize (segmented: Raw · % of frames · Log) | `heatmap.output.normalize` |
| Max value (segmented: Auto · p99.5 · Custom) | `heatmap.output.vmax` |
| Colormap (swatch grid: Inferno, Magma, Plasma, Viridis, Cividis, Turbo, Gray) | `heatmap.output.colormap` |
| Channel scale (segmented: Joint · Independent) | `heatmap.output.composite_scale` (visible for `separate`) |

### 8.4 Other tools' controls

All parameters of each tool (spec.md §6) appear in its panel, in the order of spec.md, grouped into the sections named below. Control types follow these rules:

- Choice with ≤ 5 options → segmented; more → select
- int/float with a range → slider row (log scale for rates)
- Time → time field; Duration → number + unit select
- bool → checkbox
- list of choices → checkbox group

| Tool | Sections |
|---|---|
| Timeline | Detection (link: "uses Heatmap detection settings", button "Edit in Heatmap"), Segments & peaks |
| Scenes | Cuts, Frozen frames, Black frames, Thumbnails |
| Optical flow | Motion (min magnitude), Algorithm (pyramid, window, iterations, poly n/sigma — collapsed by default), Display (colormap, arrow spacing) |
| Flicker | Analysis (window, overlap, min/max Hz, min amplitude), Display (colormap). A memory estimate line warns before W010. |
| Compare | Video B, Alignment, Difference (delta, metrics, worst), Display |
| Background | Method, Samples, Foreground frame |
| Pixel stats | Channels, Measures, Defect detection (stuck/hot/dead), Display |
| Barcode | Mode, Style, Size |
| Contact sheet | Grid, Selection, Labels, Format |
| Report | Tools checklist, Title, Self-contained |
| Video info | (no settings; Exact frame count and All streams as two checkboxes) |

### 8.5 Validation, reset and undo

- **Validation:** the server validates every change. Invalid values keep the control in an error state (red border, message below, from the core's validation text) and are not applied.
- **Reset:**
  - double-click a control's label resets that control
  - each section has **Reset section** in its summary row menu
  - the preset row can **Reset to preset**
- **Undo/redo:** every change (including preset choice, import and Apply buttons) is one step in a per-workspace history (≥ 200 steps). Ctrl/Cmd+Z undoes; Ctrl/Cmd+Shift+Z or Ctrl+Y redoes. Toasts for imports and applies include **Undo**.
- **Changed from preset:** a small dot marks the control and its section.

### 8.6 CLI command box

At the bottom of the panel: "Same run from the CLI" with a copy button. It shows the command for the current tool and file using **only non-default values**, built by the server so it matches the CLI exactly (`GET …/cli`), e.g.:

```
avideo heatmap street-cam.mp4 --space rgb --thresh 128,140,96 --hysteresis 12 --combine majority
```

It updates live as settings change. A menu offers:

- **Copy as --config**: saves `<tool>_settings.toml` to the output folder and copies `avideo heatmap street-cam.mp4 --config <path>`
- **Copy TOML**

---

## 9. Runs and live updates

- **Preview run:**
  - starts automatically when a tool opens and restarts after pipeline/input changes (debounced 200 ms)
  - runs at preview resolution with one worker
  - frames arrive in order and the viewer follows
- **Full run:** started by **Run full analysis** (or `R`). Uses full settings and parallel workers; progress and merged snapshots stream to the viewer. When it finishes, the result badge becomes `Full ✓` and the result is cached.
- **Stop:** the Stop button or Esc cancels gracefully (partial result kept, badge `Partial`). Stopping twice within 2 s hard-cancels.
- **Throttling:**
  - stage images at the live update rate (default 12 fps), snapshots at 4 fps, frame stats batched at 10 Hz
  - the server never queues frames for a slow client: latest wins, older pending frames are dropped
- **Cache:** returning to settings that were already run loads the cached result instantly (badge shows `Full ✓ · cached`).
- **Multiple tools:** each tool's latest preview and full result stay available while working in another tool. The Report page reuses existing full results.

---

## 10. Export and import (server side)

- Export writes through the core writers (spec.md §9), so file names, formats, embedded PNG metadata and `*_run.json` are identical to the CLI.
- Export of time-lapse and rolling videos reports progress over the WebSocket (`export.progress`).
- **Reveal in file manager** runs the platform opener (`xdg-open`, `open`, `explorer`) on the folder, only for allowed paths.
- Imports are uploaded to the server (max 200 MB per file, except dropped videos), detected by content (not extension alone) and handled as in 6.4.

---

## 11. Keyboard shortcuts

Active when focus is not in a text field. Shown in the `?` overlay and in tooltips.

| Group | Key | Action |
|---|---|---|
| Playback | Space | Play / pause |
| | ← / → | Previous / next frame |
| | Shift + ← / → | 10 frames back / forward |
| | Home / End | First / last frame |
| | L | Follow live |
| View | 1 … 6 | Select stage 1 … 6 |
| | S / D / B / W | Single / Side by side / Blend / Wipe |
| | [ / ] | Blend −/+10 (Wipe: divider −/+5%) |
| | 0 | Blend 50/50 |
| | F / Z | Fit / 100% |
| | + / − | Zoom in / out |
| | I | Toggle pixel inspector |
| | H | Toggle wipe orientation |
| Analysis | R | Run full analysis |
| | Esc | Stop run · cancel ROI drawing · close dialog |
| | P | Pick color (range method) |
| App | Ctrl/Cmd + O | Open |
| | Ctrl/Cmd + E / I | Export / Import |
| | Ctrl/Cmd + Z | Undo |
| | Ctrl/Cmd + Shift + Z, Ctrl + Y | Redo |
| | Ctrl/Cmd + K | Command palette |
| | ? | Shortcuts overlay |

---

## 12. API

All endpoints are under `/api`, return JSON unless noted, and require the session token (section 16). Errors return `{"error": {"code", "title", "message", "suggestion", "key"?}}` with HTTP 4xx/5xx; codes are spec.md §13.

### 12.1 REST

| Method & path | Purpose |
|---|---|
| `GET /api/version` | `{version, backend, pyav}` |
| `GET /api/schema` | All tools' parameter schemas: key, type, default, range/choices, help, long help, behavior class |
| `GET /api/preferences` · `PUT /api/preferences` | Read / update preferences |
| `GET /api/presets` · `POST /api/presets` · `DELETE /api/presets/{name}` | List / save / delete presets |
| `GET /api/fs/list?path=` | `{path, parent, entries: [{name, kind: dir\|video\|session\|settings\|results\|other, size, modified}]}` |
| `GET /api/fs/meta?path=` | Lazy per-row details: `{duration, width, height, fps}` |
| `GET /api/fs/thumb?path=&t=&w=` | JPEG thumbnail |
| `POST /api/fs/reveal` | `{path}` → opens the file manager |
| `GET /api/recent` · `DELETE /api/recent/{id}` | Recent list |
| `POST /api/workspaces` | `{path}` or `{session}` → `{id, meta, info, warnings, settings: {tool: …}, results: {tool: {preview, full}}}` |
| `GET /api/workspaces/{id}` · `DELETE /api/workspaces/{id}` | Read / close |
| `GET /api/workspaces/{id}/settings` | All tools' resolved settings |
| `PATCH /api/workspaces/{id}/settings` | `{tool, patch, preset?}` → `{resolved, errors, class}`; the server restarts the preview run as the class requires |
| `POST /api/workspaces/{id}/undo` · `…/redo` | History steps (server-side history so all tabs agree) |
| `GET /api/workspaces/{id}/cli?tool=` | `{command, command_with_config, toml}` |
| `POST /api/workspaces/{id}/runs` | `{tool, quality}` → `{run_id}` |
| `GET /api/runs/{run_id}` · `DELETE /api/runs/{run_id}?hard=` | Status / stop |
| `GET /api/runs/{run_id}/files/{name}` | A result or output file (npy, csv, png, json) |
| `GET /api/workspaces/{id}/frames/{index}/{stage}?tool=&w=` | One stage image (WebP/JPEG), for thumbnails and fallbacks |
| `POST /api/workspaces/{id}/export` | `{scope, items: [{id, options}], dest}` → `{job_id}`; result via WebSocket |
| `POST /api/import` | multipart file or `{path}` → `{kind, applied, workspace?, warnings}` |
| `POST /api/workspaces/{id}/report` | `{tools, title}` → `{run_id}` |

### 12.2 WebSocket — `/api/ws`

One connection per tab. Messages are JSON text frames or binary frames.

**Binary framing:** `[uint32 big-endian header length][header JSON, UTF-8][payload bytes]`.

**Client → server:**

| Type | Fields | Purpose |
|---|---|---|
| `hello` | `workspace`, `resume_seq?` | Attach to a workspace; resume after reconnect |
| `subscribe` | `tool`, `stages`, `size: [w, h]`, `fps`, `snapshot_fps` | What to stream for the visible tool |
| `inspect` | `id`, `tool`, `frame`, `stages`, `size` | Frame inspector request; a newer `inspect` cancels older ones |
| `playback` | `state: play\|pause`, `frame`, `speed` | Post-run playback |
| `follow` | `on` | Follow live on/off |
| `ping` | | Keep-alive (every 15 s) |

**Server → client (JSON):**

`run.started`, `run.progress`, `frame.stats` (batched rows), `warning`, `run.finished`, `run.cancelled`, `run.failed`, `settings.changed` (from another tab or an import), `export.progress`, `export.done`, `inspect.done`, `pong`.

Fields mirror the core live events (spec.md §11). Every message carries an increasing `seq`.

**Server → client (binary):**

| `kind` in header | Header fields | Payload |
|---|---|---|
| `stage` | `tool`, `stage`, `frame`, `w`, `h`, `mime` (`image/webp` or `image/jpeg`), `inspect_id?` | Encoded image (quality 85) |
| `snapshot` | `tool`, `frames_done`, `w`, `h`, `channels`, `dtype: uint16`, `max`, `hist` (1024-bin histogram for percentile `vmax`) | Raw little-endian `uint16` values scaled to `max` |

- Image size is the viewer's canvas size × devicePixelRatio, capped at 1920 px wide.
- Snapshots are sent at processing resolution, capped at 1280 px wide (downsampled by summing).

---

## 13. Performance budgets

| Interaction | Budget |
|---|---|
| App shell load (localhost, cold) | ≤ 300 ms; zero external requests |
| Open video → first frame visible | ≤ 1 s |
| Open video → first live heatmap update | ≤ 1.5 s |
| Display-class change → painted | ≤ 16 ms |
| Pipeline change while paused → stage image updated | ≤ 150 ms at preview size |
| Pipeline change while running → first update of the restarted preview | ≤ 500 ms |
| Pan, zoom, blend, wipe | 60 fps |
| JavaScript shipped | ≤ 300 KB uncompressed, excluding fonts |
| Browser memory | ≤ 500 MB |

---

## 14. States

| State | Presentation |
|---|---|
| No video | Open screen |
| Loading video | Viewer skeleton with file name and "Reading metadata…" |
| Running | LIVE chip, progress tile, sidebar progress ring, primary button becomes **Stop** |
| Result outdated | Badge `Full · outdated` and a dot next to the tool |
| Partial | Badge `Partial · stopped at N%` |
| Invalid setting | Control error state with message; the change is not applied |
| Run failed | Error card in place of the viewer content (title, message, suggestion, **Copy details**); toast |
| Decode / stabilization warnings | Dismissible warning banner at the top of the viewer with a count |
| Connection lost | Top banner "Connection to avideo lost — reconnecting…"; auto-retry with backoff; on reconnect the state is resynced (`resume_seq`) |
| Server stopped | Banner "The avideo server stopped. Start it again with `avideo serve`." |
| Empty results | E.g. Scenes with no cuts: an illustration-free message with the most relevant setting to change |

---

## 15. Accessibility

- WCAG 2.1 AA in both themes.
- Every control is a real `<button>`, `<input>`, `<select>` or `<a>` with a visible label or `aria-label`. Tab order follows the visual order. The focus ring is 2 px `--accent`, always visible on keyboard focus.
- Segmented controls are button groups with `aria-pressed`; tabs use `role="tablist"`.
- Sliders are native range inputs with `aria-valuetext` (e.g. "Delta 12", "Blend: both 50%").
- The viewer canvas has `role="img"` and an `aria-label` describing the current stage and frame. A polite live region announces run start, finish, failure and imports.
- Color is never the only signal: warnings have icons, selected states change background and weight, and the scrubber's played part also has the playhead.
- `prefers-reduced-motion`: no spinner rotation (static indicator), no smooth scrolling.
- Color-blind friendly colormaps (Cividis, Viridis) are always offered.

---

## 16. Security

- **Bind:** `127.0.0.1` by default; other hosts only with `--allow-remote`.
- **Session token:**
  - a random 128-bit token is created at every server start and included in the opened URL (`?t=…`)
  - on first load it is exchanged for an `HttpOnly`, `SameSite=Strict` cookie and removed from the address bar
  - every API and WebSocket request requires it
- **Host and Origin checks:**
  - the `Host` header must be `127.0.0.1:<port>` or `localhost:<port>` (protects against DNS rebinding), unless `--allow-remote`
  - the WebSocket and all non-GET requests require a matching `Origin`
- **File system:**
  - browsing and reading are limited to `--root`; paths are resolved to real paths, and symlinks pointing outside the root are rejected
  - writes are limited to the output root and avideo's config, data and cache folders
  - uploaded files go to `<cache>/uploads/` with sanitized names
- **Content Security Policy:** `default-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-src 'self'; object-src 'none'`. The report preview iframe is sandboxed.
- **No external resources:** fonts and scripts are bundled; nothing is fetched from the internet.

---

## 17. Testing (web)

- **API:** every endpoint with FastAPI's test client. This includes token, Host and Origin enforcement, path traversal attempts (`..`, symlinks, absolute paths outside the root), validation errors, undo/redo and preset handling.
- **WebSocket:** subscribe/stream, inspect latest-wins cancellation, run lifecycle (start, progress, finish, cancel, fail), reconnect with `resume_seq`, multi-tab `settings.changed`.
- **Frontend unit tests:** store and undo history; schema-driven panel generation (every key of every tool has a control or is listed as export-only); normalization and colormap math checked against shared test vectors also used by the Python tests.
- **End-to-end (Playwright):**
  1. open a synthetic video
  2. move a threshold slider while paused and see the Thresholded stage change
  3. switch view modes, blend and wipe
  4. run full analysis and export
  5. assert the files exist and match a CLI run with the same settings
- **Visual regression:** screenshots of the Open screen, Heatmap workspace (each view mode), Export dialog and each tool page in dark and light themes at 1440 px and 390 px widths.
- **Performance checks** against section 13 (not blocking).
