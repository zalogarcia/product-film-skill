# Third party notice: brag

Parts of this starter adapt code and method from **brag** (https://github.com/latent-spaces/brag, commit `c893c5ed`), under the MIT license below:

- `tools/audio/beats.py` adapts `skills/brag/scripts/analyze_music_cues.py` (the intensity formula and the strong cue selection).
- `src/beatSync.ts` follows the beat sync rules of `skills/brag/references/step-3-compose.md`.
- `tools/audio/rate_sfx.py` follows the rating method of `skills/brag/assets/sfx/sfx-analysis.md`.
- `pipeline/poster-frame0.sh` follows the "bake the poster as frame 0" step of `skills/brag/references/step-4-deliver.md`.
- The reading time rule in `src/captionPages.ts` comes from `skills/brag/references/step-2-plan.md`.

```
MIT License

Copyright (c) 2026 Shunit Haviv Hakimi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
