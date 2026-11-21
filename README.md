# Holosii (Голосій)

A local tool for reviewing and fixing game voice-over by ear: original and translated takes side by side,
“OK” / “Fix” marks with comments, gain and normalization edits right on the waveform (with undo),
a fix queue handled by an AI coding agent, and per-folder “ready to embed” marks.

## An add-on over an AI coding agent

Holosii does not generate or edit voice-over itself. It is a review layer on top of an AI coding agent:
you listen, mark a line “Fix” and write what is wrong; Holosii queues the job and hands it to the agent
together with the files, the line text, your comment and the chosen reference original. The agent does
the actual work in your project (regenerating takes, aligning pauses, matching loudness) following a
per-project brief, and Holosii shows you the result for the next listen.

- **Claude Code** — supported now. Holosii keeps one persistent `claude` session per app run, shows its
  context size and lets you compact it.
- **Codex** — planned (see [ROADMAP.md](ROADMAP.md)).

## Running

- **macOS app:** `zsh mac/build.sh` builds `Holosii.app` next to `server.py`. The app starts the server
  itself and stops it (together with the agent) on ⌘Q. If a server is already running, it just attaches.
- **Windows app:** `powershell -ExecutionPolicy Bypass -File win\build.ps1` builds `Holosii.exe` next to
  `server.py` (see [Windows](#windows) below).
- **Without the app:** `python3 server.py` (or `Holosii.command`; on Windows `Holosii.bat`), then open
  http://localhost:8765.

Requirements: Python 3.10+, `ffmpeg` / `ffprobe`; for the fix queue — [Claude Code](https://claude.com/claude-code) (`claude`).

The interface is in Ukrainian for now.

### Windows

The Windows version is the same server with a thin C# + WebView2 window (`win/`), like `mac/` for macOS.

- **Install:** Python 3.10+ from python.org (with the `py` launcher), `ffmpeg` (`winget install Gyan.FFmpeg`),
  [Claude Code](https://claude.com/claude-code) for the fix queue. The WebView2 Runtime is part of Windows 11
  (Windows 10: install it from Microsoft).
- **Build:** .NET 8 SDK (`winget install Microsoft.DotNet.SDK.8`), then
  `powershell -ExecutionPolicy Bypass -File win\build.ps1` → `Holosii.exe` next to `server.py`. It needs the
  .NET 8 Desktop Runtime; `-SelfContained` bundles the runtime into the exe instead. CI builds it too
  (`.github/workflows/windows.yml`, artifact `Holosii-windows`).
- **What the app does:** starts `py -3 -X utf8 server.py --no-open --stdin-stop` (or attaches to a running
  server), shows http://localhost:&lt;port&gt;, allows the microphone for localhost only, opens other links in
  the default browser, and stops the server with the agent when the window closes (it closes the server's
  stdin; a Job Object makes sure nothing is left running even if the app crashes). Server log:
  `logs\app_server.log`. `HOLOSII_PYTHON` / `HOLOSII_SERVER_DIR` override the Python and the server folder.
- **Differences from macOS** (all in `platform_util.py`): “Показати у Провіднику” instead of Finder; the
  folder dialog is the Windows one; old versions and rotated logs go to `%LOCALAPPDATA%\Holosii\Trash\`
  instead of `~/.Trash/`, and entries older than 7 days are moved from there to the Recycle Bin; tools are
  looked up on `PATH` and in the winget / scoop / Chocolatey / npm folders instead of Homebrew.

## Projects

Projects are added in the UI (the “+” button) and stored in `projects.json` (not tracked; see
`projects.example.json`). A project is a folder of lines: a folder per line with `en.wav` / `ja.wav`
(originals) and `ua.wav` (translation), or flat files like `Name_en.wav` / `Name_ua.wav`.
Feedback is stored in `summary.json` inside the project folder.

Project fields:
- `agent_cwd`, `agent_brief` — the folder the agent works in and its brief (without them the queue is off);
- `default_ref` — the original language used as the agent's reference by default
  (can be changed per line with the “reference” buttons under the originals);
- `usage_cmd`, `usage_label` — optional command that prints the generation service's credit counter as JSON
  `{"used": …, "limit": …, "reset": <unix time>}` (e.g. a small script that asks ElevenLabs with the
  project's own key). Holosii runs it before and after each agent job and shows the difference as the
  generation cost; the remaining credits appear on the left rail. API keys stay in the project — Holosii
  never reads them.

**A project straight from a game.** “New project → From a game” opens a setup window with its own agent
(`setup_agent.py`, Opus by default): it surveys the game folder (read-only), shows a plan with sample lines, and
after your “yes” extracts every voice line into `listen/` and writes the project's `tools/extract.py`,
`tools/pack.py` and `BRIEF.md`. What it knows about engines lives in `recipes/` (Unreal + Wwise first). It never
looks for encryption keys or bypasses protection. “← Проєкти” takes you back to the project list from anywhere.

The left rail also shows the **Claude plan limits**: how much of the 5-hour window is used (big number) and of
the week (below), with reset times in the tooltip. Holosii takes them from Claude Code's own stream
(`rate_limit_event`), so it never touches your login; click the block to refresh. Before a job is sent at
≥ 90 % (or when a limit is reached) Holosii asks first.

Audio, API keys and local data (queue, logs, edit history) never go into the repository — see `.gitignore`.

## Tempo without pitch change

Under the volume row: “Довжина ±%” changes the tempo of the whole file or of the selected region, and
“Довжина як EN/JA” stretches or squeezes the whole file to the reference length; quick “−5% / +5%” buttons
appear on a selection. The pitch stays the same (ffmpeg `atempo`, clean for speech within about ±25 %);
⌘Z undoes. The same is available from the command line for agents and scripts:

```
python3 tempo.py in.wav out.wav --speed 1.1                     # 10 % faster (shorter)
python3 tempo.py in.wav out.wav --length 3.2                    # whole file 3.2 s long
python3 tempo.py in.wav out.wav --speed 0.9 --start 1 --end 2.5 # only that region, slower
```

## Dictation

The “Диктувати” button next to the comment (or the D key) records your voice and a **local Whisper**
(whisper.cpp `whisper-cli` + a multilingual ggml model in `~/.cache/whisper/`) turns it into text at the cursor.
Nothing leaves the machine. Without Whisper the button is disabled; hovering it explains why and links to the
install guide at `/docs/whisper.html` (`static/docs/`). Settings: `dictation_lang` (default `uk`),
`whisper_model`, `dictation_prompt` (names Whisper should spell right). On Windows put `whisper-cli.exe` on
`PATH` (or in `%LOCALAPPDATA%\Programs\whisper-cpp\`); models are looked up in `~/.cache/whisper/` as well.

## Echo

“Луна” row: amount (%) and tail (seconds until it dies out), for the whole file or the selected region (a
quick “Луна” button appears on a selection). The loudness of the words stays the same; ⌘Z removes it.
10 % is barely audible, 30 % a room, 70 % a large hall. From the command line:

```
python3 echo.py in.wav out.wav --amount 30 --tail 1.0
python3 echo.py in.wav out.wav --amount 50 --tail 2 --start 1 --end 2.4
```

## After each agent job

Holosii keeps the version the agent overwrote (“▶ До правки” plays it, ⌘Z restores it) and measures pitch,
loudness and length of the new file, the previous version and the reference. Pitch is compared with the
previous version (same voice; the reference is usually another actor in another language, shown greyed for
information), loudness and length with the reference. Large differences (e.g. a pitch-shifted voice or a much
quieter take) are flagged next to the agent's reply, together with the job's token count and cost. A job that
goes over `max_job_tokens` is stopped.

## Settings (`settings.json`, created on first run)

- `model` — agent model; `timeout_min` — minutes per job; `max_job_tokens` — token limit per job;
- `auto_compact_at` — compact the agent's context above this size;
- `port` — server port (default 8765; the `PORT` environment variable wins). Holosii.app reads the same file.
- `agent_sandbox` (default `false`) — run the agents' Bash in Claude Code's sandbox (macOS / Linux; not available
  on native Windows): writes only to the project folders, the agent's work folder, `$TMPDIR` and the trash;
  network only to `agent_sandbox_domains` (default `["api.elevenlabs.io"]`); a command that needs more fails
  instead of running unsandboxed. Turn it on once your project's tools work inside it.

## Security

The fix agent runs shell commands as you, so the server guards who can reach it:

- **Other websites:** the server listens on 127.0.0.1 only and refuses requests whose Host is not localhost
  (DNS rebinding), POSTs from other origins and non-JSON POSTs (CSRF), so a page open in your browser cannot
  queue jobs for the agent.
- **Other programs and other users of this computer:** every request except the page shell and `/api/ping`
  needs an access key. The server creates it once in a file only you can read
  (`~/Library/Application Support/Holosii/token` on macOS, `%LOCALAPPDATA%\Holosii\token` on Windows).
  Holosii.app / Holosii.exe and `python3 server.py` open the page as `/?t=<key>`; the server turns it into an
  `HttpOnly; SameSite=Strict` cookie and redirects to `/`. A tab without the key shows how to open Holosii.
  To revoke all sessions delete the file and restart the server. **After updating, rebuild Holosii.app**
  (`zsh mac/build.sh`) — older builds do not send the key.
- **The page:** strict Content-Security-Policy (own scripts only, no framing), `nosniff`,
  `Cross-Origin-Resource-Policy: same-origin`; POST bodies are capped at 64 MB.
- **The app windows** grant the microphone and open pages only for Holosii's own `localhost:<port>`; any other
  link, including other local servers, opens in the default browser.
- **The agents** read game files and line texts, which could try to steer them (prompt injection). Turn on
  `agent_sandbox` to keep their Bash inside the project folders and an allow-list of domains.

## Tests

`python3 -m unittest discover -s tests` — starts real servers on free ports with a temporary project and a
fake agent (`tests/fake_agent.py`). Requires ffmpeg. `tests/test_platform.py` covers `platform_util.py`.
GitHub Actions runs the tests on Windows and macOS and builds `Holosii.exe` (`.github/workflows/windows.yml`).
