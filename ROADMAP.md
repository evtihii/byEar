# ByEar — roadmap

Ideas for later: planned ahead, not implemented yet unless checked.

## Agents
- [x] **Claude Code** as the fix agent: one persistent `claude` session per app run, context meter, compact. (2026-11-19)
- [ ] **Codex** as an alternative agent. Make the agent layer pluggable (start / send job / interrupt /
  compact / context size), pick the agent per project in `projects.json`.

## Originals in several languages
- [x] Several original tracks per line (`en.wav`, `ja.wav` …), an “Original” group separate from
  “Translation · UA”. (2026-11-19)
- [x] “Reference for the agent” toggle buttons under the originals: one language or none; the choice is
  remembered in `summary.json` (`items[id].ref`, `"none"` = no reference), the default is the project's
  `default_ref` in `projects.json`. Sent to the agent as job fields (`ref`, `ref_file`), not as comment text. (2026-11-19)
- [ ] **Japanese transcript in `текст.txt`.** Today it holds an “English (audio): …” line. Add the same line
  for Japanese (Scribe, `language_code='ja'`) and maybe a literal translation for the reviewer.
- [ ] **Japanese originals for SILENT HILL f.** Extract the Japanese voice-over from the game pak
  (`WwiseAudio/…/Japanese`) and put `ja.wav` next to `en.wav` in the listening folders. Without it the JA
  button does not appear.

## App
- [x] **ByEar.app for macOS** (2026-11-19): a Swift shell around WKWebView (`mac/main.swift`, build with
  `zsh mac/build.sh`). Starts `server.py --no-open` itself, ⌘Q stops the server and the agent; if a server
  is already running it only attaches and leaves it alone.
- [ ] **Windows** (not now). Plan: the same thin shell in C# + WebView2. Before that, move the three
  macOS-specific spots in the server into a separate module — folder picker (`osascript`), Trash (`~/.Trash`),
  “Reveal in Finder” (`open -R`) — and add Windows versions (Recycle Bin, Explorer). Ship Python and ffmpeg
  alongside or inside the installer. Build on a Windows machine or in CI.
- [ ] English UI (the interface is Ukrainian for now).

## Quality and safety (found 2026-11-19)
- [x] **Reject cross-site requests.** Host must be localhost/127.0.0.1/[::1] with our port; POSTs must come
  from the ByEar page (Origin) and carry `application/json` — blocks CSRF and DNS rebinding.
- [x] **Verify agent results automatically.** After each job ByEar measures pitch (f0), loudness (LUFS) and
  length of the new file, the version before the edit and the reference (`analysis.py`, no numpy), and flags
  large differences next to the agent's reply.
- [x] **Previous version A/B.** The version an agent overwrote is kept (`before/`, pushed to undo history):
  “▶ До правки” plays it, ⌘Z restores it.
- [x] **Cost visible and capped.** Tokens/cost in the agent reply card; `max_job_tokens` in `settings.json`
  (default 1 000 000) stops a job that goes over.
- [x] `index.html` split into `static/app.css` + `static/js/*.js`; server tests in `tests/`.
- [x] Port from `settings.json` (`port`) or `PORT` (server and ByEar.app); old logs and “before” copies rotate
  to the Trash; language tags and names come from the server (`/api/config`), a project can add `lang_names`.
- [x] **Generation cost per job** (2026-11-20): credits spent on the generation service (ElevenLabs) via the
  project's `usage_cmd`, shown in orange next to the Claude cost; remaining credits on the left rail.
- [x] **Tempo without pitch change** (2026-11-20): whole file, a region, or fit to the reference length;
  `tempo.py` also works from the command line. Higher quality (rubberband) if ffmpeg is built with it.
- [ ] Detect original audio pasted into the translation (e.g. English breaths) — needs audio fingerprinting.

## Other
- [ ] Documentation link on the home page (`DOCS_URL` in `index.html`, empty for now).
- [ ] Paths to sound banks per project (postponed).
