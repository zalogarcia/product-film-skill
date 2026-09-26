# Sound effects: CC0 1.0 (public domain)

Every sound file under `assets/sfx/kenney/` is by **Kenney** (www.kenney.nl), released under **Creative Commons Zero, CC0 1.0 Universal**: http://creativecommons.org/publicdomain/zero/1.0/

Each pack's own `License.txt` sits unmodified next to its files and says:

> This content is free to use in personal, educational and commercial projects.
> Support us by crediting Kenney or www.kenney.nl (this is not mandatory)

The full CC0 1.0 legal code is in `CC0-1.0.txt`. Credit is not required; when a film's description has room, "Sound effects: Kenney (kenney.nl), CC0" is a courtesy.

## The files

| File | Pack | Page | Used for |
|------|------|------|----------|
| `kenney/interface-sounds/confirmation_002.ogg` | Interface Sounds (1.0) | https://kenney.nl/assets/interface-sounds | `notify` |
| `kenney/interface-sounds/select_001.ogg` | Interface Sounds (1.0) | https://kenney.nl/assets/interface-sounds | `tick` |
| `kenney/casino-audio/card-slide-2.ogg` | Casino Audio (1.1) | https://kenney.nl/assets/casino-audio | `whoosh` |
| `kenney/impact-sounds/impactSoft_heavy_002.ogg` | Impact Sounds (1.0) | https://kenney.nl/assets/impact-sounds | `hit` |

`manifest.json` lists each file with its pack, the official zip it came from and that zip's SHA-256, the file's own SHA-256, its licence, and its rating. `npm run sfx` reads it to record each sound's source and licence in `build/SOURCES.txt`.

## Adding a sound

`python3 tools/audio/fetch_kenney.py` downloads the full Kenney library (7 packs, 521 sounds, about 11 MB) and checks every zip against its SHA-256; `tools/audio/rate_sfx.py` rates it for the four kinds of effect the starter uses. Copy the one you choose here with its pack's `License.txt`, add it to `manifest.json` with its SHA-256, and point the effect's `file` at it in `film.config.json`. A sound from anywhere else needs its own licence file and manifest entry the same way; one that is not listed is recorded as LICENCE UNKNOWN and fails `npm run check:final -- --publish`.
