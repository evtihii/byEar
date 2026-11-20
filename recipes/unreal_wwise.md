# Unreal Engine `.pak` + Wwise

Worked out on SILENT HILL f (UE5, pak version 11, part of the entries Oodle-compressed). Other UE4/UE5 games
with Wwise look the same from the bank level down; the container (pak vs IoStore) can differ.

## Recognise it
- `<Game>/Content/Paks/*.pak` (and maybe `*.utoc` / `*.ucas` = IoStore, newer UE5).
- Inside: `.../WwiseAudio/Event/...*.bnk`, `.../Media/<Language>/...*.wem` (or `.../WwiseAudio/<Language>/`).
- Pak footer magic `0x5A6F12E1` at the end of the file; the version is right after it.
- Encrypted index (footer flag) → stop: needs an AES key, out of scope.

## Tools
- `ffmpeg`, `vgmstream-cli` (decodes `.wem`, `.bnk`-embedded media) — Homebrew.
- Pak reading: write a small reader (index → entries: name, offset, size, compression), or use an open-source
  one such as `repak` (Rust) if it reads the version. IoStore: `retoc`.
- Oodle-compressed entries need an Oodle decoder (e.g. the open-source `ooz`); if none is available, list those
  entries in the plan and go on with the rest.

## Where the voice is
- **Gameplay lines:** one event bank per line, e.g. `Event/<Language>/<xx>/Play_VO_*.bnk`. In the bank's `HIRC`
  chunk a Sound object (type 2) holds the media id (u32 at +14 from the object start) and the plugin id; the
  audio is `Media/<Language>/<first 2 digits of id>/<id>.wem` (Vorbis, usually stored uncompressed in the pak).
- **Cutscenes:** often music-track objects (type 0x0b) in `Play_LS_*`/scene banks, with one source per voice
  language; multichannel (5.1/7.1), voice in the centre channel.
- **Other languages** (e.g. Japanese) live in a parallel language folder. The Japanese bank for the same event
  has the Japanese media id at the same offset as the English one in the English bank.
- **Text:** subtitles are in `Localization/Game/<lang>/Game.locres`. Event names usually do NOT equal subtitle
  keys; match by transcribing the original audio (Whisper) or by naming patterns, and say how sure you are.

## Extract (what the listening folders look like)
`listen/<group>/<NNN>_<key>/en.wav` (+ `ja.wav` …), `текст.txt` with the original text (subtitle and/or
transcript). Group by chapter/scene when the names show it. Decode with `vgmstream-cli -o out.wav in.wem`;
keep the original channel count for cutscene stems, mono for gameplay lines.

## Pack (replacing a line)
- Write the new line as a Wwise **PCM** `.wem`: RIFF/WAVE, `fmt ` = WAVEFORMATEXTENSIBLE (`0xFFFE`, 16-bit, the
  original rate and channel config).
- In the event bank set the Sound's plugin id to PCM `0x00010001` and its media size to the new size. For
  streamed cutscene sources also stream type = 2 and prefetch size = 0.
- Build a mod pak (same pak version, uncompressed, mount point as the original), named so it loads last, e.g.
  `zzz_<Lang>_Voice_P.pak`; it goes into `Content/Paks/~mods/`. UE pak v11 index: FNV-64 path hashes of the
  lower-case UTF-16LE path, SHA-1 of the index blocks.
- Pak offsets are 32-bit in some index fields → split mods bigger than ~3.8 GB into several paks.
- Check every changed `.wem` decodes (`vgmstream-cli -m`), and that only the intended files changed against the
  previous build (index and content).

## Pitfalls seen
- Game must be closed while the pak in `~mods` is replaced.
- Under Wine/CrossOver the game folder is inside the bottle (`drive_c/Program Files (x86)/Steam/steamapps/common/…`).
- Wwise language folder names have spaces/parentheses (`English(US)`) — quote paths.
