#!/usr/bin/env bash
# Bake a designed poster into FRAME 0 of a finished video, and prove nothing else moved.
#
#   bash pipeline/poster-frame0.sh <in.mp4> <out.mp4> (--at <seconds> | --image <poster.png>) [--crf N] [--force] [--lossless]
#
#   --at S       use the video's own frame at S seconds (pick a SETTLED frame: text fully in,
#                not mid transition). Snapped to the nearest frame; extracted losslessly in the
#                video's native pixel format, so frame 0 becomes that exact frame.
#   --image P    use a still (scaled to fit the video, letterboxed if the aspect differs).
#   --crf N      x264 quality of the re-encode (default 16; lower is better and bigger).
#   --force      allow overwriting an existing <out.mp4> (never <in.mp4>, that is refused).
#   --lossless   x264 qp 0 (High 4:4:4 Predictive). PROOF MODE ONLY: frames 1+ decode
#                bit identical to the input. Many phones cannot play it; never deliver it.
#
# `npm run poster` (and so `npm run finish`) runs this for every cut; you can also run it on
# any H.264 file by hand.
#
# Why: X, Slack, Discord and most players show frame 0 as the idle thumbnail and ignore
# cover art metadata, so a first frame that is dark or half animated becomes the thumbnail.
# The poster shows for one frame (33 ms at 30 fps) on playback, and is what every grabber sees.
# The technique follows latent-spaces/brag, skills/brag/references/step-4-deliver.md
# (MIT; the notice is in tools/audio/NOTICE-brag.md).
#
# Output: <out.mp4> (H.264, same size, fps, frame count, pixel format and range as the
# input, audio stream COPIED), plus <out-stem>.poster.png next to it (the custom thumbnail
# for platforms that take an upload). Never writes to <in.mp4>.
#
# Verification runs every time and the script exits 1 if any check fails:
#   same width, height, fps, frame count, video duration; audio packets identical (md5);
#   frame 0 matches the poster (PSNR >= 40 dB; exact in --lossless; when the old frame 0
#   already was the poster, it says so); frames 1..N-1 match the input (min PSNR >= 40 dB;
#   every frame hash equal in --lossless).
set -euo pipefail

usage() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
die() { echo "poster-frame0: $*" >&2; exit 2; }

[ $# -ge 2 ] || usage
IN="$1"; OUT="$2"; shift 2
AT=""; IMG=""; FORCE=0; LOSSLESS=0; CRF=16
while [ $# -gt 0 ]; do
  case "$1" in
    --at) AT="${2:?--at needs seconds}"; shift 2 ;;
    --image) IMG="${2:?--image needs a file}"; shift 2 ;;
    --crf) CRF="${2:?--crf needs a number}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --lossless) LOSSLESS=1; shift ;;
    *) usage ;;
  esac
done
[ -n "$AT" ] || [ -n "$IMG" ] || die "pick the poster: --at <seconds> (a settled frame) or --image <png>"
[ -z "$AT" ] || [ -z "$IMG" ] || die "--at and --image are exclusive"
[ -f "$IN" ] || die "no such input: $IN"
[ -z "$IMG" ] || [ -f "$IMG" ] || die "no such image: $IMG"
case "$CRF" in ''|*[!0-9]*) die "--crf needs a whole number, got $CRF";; esac
abs() { (cd "$(dirname "$1")" && printf '%s/%s\n' "$(pwd -P)" "$(basename "$1")"); }
mkdir -p "$(dirname "$OUT")"
[ "$(abs "$IN")" != "$(abs "$OUT")" ] || die "refusing to overwrite the input; write next to it (e.g. <name>-poster.mp4)"
[ ! -e "$OUT" ] || [ "$FORCE" = 1 ] || die "$OUT exists; pass --force to replace it"

FF=(ffmpeg -hide_banner -nostdin -loglevel error -y)
probe() { ffprobe -v error -select_streams "$1" -show_entries "$2" -of default=nw=1:nk=1 "$3" | head -1; }
count_frames() { ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of default=nw=1:nk=1 "$1"; }
audio_md5() { if [ -n "$(probe a:0 stream=index "$1")" ]; then "${FF[@]}" -i "$1" -map 0:a:0 -c copy -f md5 - 2>/dev/null; else echo "no-audio"; fi; }

W=$(probe v:0 stream=width "$IN"); H=$(probe v:0 stream=height "$IN")
RATE=$(probe v:0 stream=r_frame_rate "$IN"); PIX=$(probe v:0 stream=pix_fmt "$IN")
RANGE=$(probe v:0 stream=color_range "$IN"); SPACE=$(probe v:0 stream=color_space "$IN")
PRIM=$(probe v:0 stream=color_primaries "$IN"); TRC=$(probe v:0 stream=color_transfer "$IN")
VDUR=$(probe v:0 stream=duration "$IN"); NF=$(count_frames "$IN")
FPS=$(awk -v r="$RATE" 'BEGIN{split(r,a,"/"); printf "%.6f", a[1]/(a[2]?a[2]:1)}')
[ "$RANGE" = "pc" ] || [ "$RANGE" = "tv" ] || RANGE="tv"
case "$PIX" in yuv420p|yuvj420p|yuv422p|yuv444p) ;; *) die "unsupported pixel format $PIX (expected a yuv h264 delivery)";; esac
echo "input: ${W}x${H} @ ${RATE} fps, ${NF} frames, video ${VDUR} s, ${PIX} range=${RANGE} matrix=${SPACE}"

TMP=$(mktemp -d "${TMPDIR:-/tmp}/poster-frame0.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PNG="${OUT%.*}.poster.png"
MATRIX=$([ "$SPACE" = "bt470bg" ] || [ "$SPACE" = "smpte170m" ] && echo bt601 || echo bt709)

# The poster is never written to an intermediate file: an intermediate codec can refuse the
# input's pixel format or range and silently convert it (ffv1 turns full range yuvj420p into
# tv range). It is a second input of the SAME graph instead, and the verify step below
# rebuilds it with the exact same input + chain, so "frame 0 == poster" compares like with like.
if [ -n "$AT" ]; then
  K=$(awk -v t="$AT" -v f="$FPS" 'BEGIN{printf "%d", t*f+0.5}')
  [ "$K" -lt "$NF" ] || die "--at $AT is past the last frame ($NF frames)"
  [ "$K" -ge 1 ] || die "--at $AT resolves to frame $K; frame 0 is what gets replaced, so pick a settled frame at or after frame 1"
  # accurate seek: the first frame at or after (K - 0.5) / fps is frame K
  SS=$(awk -v k="$K" -v f="$FPS" 'BEGIN{s=(k-0.5)/f; if (s<0) s=0; printf "%.6f", s}')
  PIN=(-ss "$SS" -i "$IN")
  PCHAIN="trim=end_frame=1,setpts=PTS-STARTPTS"
  "${FF[@]}" "${PIN[@]}" -frames:v 1 -vf "scale=in_range=$RANGE:in_color_matrix=$MATRIX,format=rgb24" "$PNG"
  echo "poster: input frame $K (t=$(awk -v k="$K" -v f="$FPS" 'BEGIN{printf "%.3f", k/f}') s)"
else
  PIN=(-i "$IMG")
  SWS="bicubic+accurate_rnd+full_chroma_int"
  FIT="scale=${W}:${H}:force_original_aspect_ratio=decrease:flags=$SWS,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=black"
  # formats AND scaler flags pinned at every step: a -vf graph and a -filter_complex graph
  # otherwise get different default swscale flags and round differently (up to 2 levels).
  # The poster is also tagged with the INPUT's colorspace (unknown stays unknown): a
  # mismatched tag makes the overlay insert a YUV->RGB->YUV conversion that shifts colour on
  # untagged video, and the psnr check would inherit the same conversion and miss it.
  PSPACE=$([ -z "$SPACE" ] && echo unknown || echo "$SPACE")
  PCHAIN="format=rgb24,$FIT,format=rgb24,scale=out_range=$RANGE:out_color_matrix=$MATRIX:flags=$SWS,format=$PIX,setparams=colorspace=$PSPACE,trim=end_frame=1,setpts=PTS-STARTPTS"
  "${FF[@]}" -i "$IMG" -vf "$FIT,format=rgb24" -frames:v 1 "$PNG"
  echo "poster: image $IMG"
fi

if [ "$LOSSLESS" = 1 ]; then VENC=(-c:v libx264 -qp 0 -preset ultrafast); else VENC=(-c:v libx264 -crf "$CRF" -preset slow); fi
# keep every input timestamp: -fps_mode on ffmpeg 5.1 and newer, -vsync before it
# (the help is captured first: `| grep -q` would end the pipe early and, under pipefail, fail)
FFHELP="$(ffmpeg -hide_banner -h full 2>/dev/null || true)"
case "$FFHELP" in *-fps_mode*) SYNC=(-fps_mode passthrough) ;; *) SYNC=(-vsync passthrough) ;; esac
# carry the input's colour tags onto the output frames (the encoder takes them from the frames)
PARAMS="range=$RANGE"
[ "$SPACE" = "unknown" ] || [ -z "$SPACE" ] || PARAMS="$PARAMS:colorspace=$SPACE"
[ "$PRIM" = "unknown" ] || [ -z "$PRIM" ] || PARAMS="$PARAMS:color_primaries=$PRIM"
[ "$TRC" = "unknown" ] || [ -z "$TRC" ] || PARAMS="$PARAMS:color_trc=$TRC"
# ... and name them to the encoder as well: ffmpeg before 5 does not pass frame tags to libx264
CTAGS=(-color_range "$RANGE")
[ "$SPACE" = "unknown" ] || [ -z "$SPACE" ] || CTAGS+=(-colorspace "$SPACE")
[ "$PRIM" = "unknown" ] || [ -z "$PRIM" ] || CTAGS+=(-color_primaries "$PRIM")
[ "$TRC" = "unknown" ] || [ -z "$TRC" ] || CTAGS+=(-color_trc "$TRC")

"${FF[@]}" -i "$IN" "${PIN[@]}" \
  -filter_complex "[1:v]$PCHAIN[p];[0:v][p]overlay=0:0:enable='eq(n,0)':eof_action=repeat,setparams=$PARAMS[v]" \
  -map "[v]" -map "0:a?" "${VENC[@]}" -pix_fmt "$PIX" "${CTAGS[@]}" "${SYNC[@]}" \
  -c:a copy -movflags +faststart "$TMP/out.mp4"
mv "$TMP/out.mp4" "$OUT"

# ---------------------------------------------------------------- verification
fail=0
check() { if [ "$2" = "$3" ]; then echo "  ok    $1: $2"; else echo "  FAIL  $1: in=$2 out=$3"; fail=1; fi; }
echo "verify:"
check "size" "${W}x${H}" "$(probe v:0 stream=width "$OUT")x$(probe v:0 stream=height "$OUT")"
check "fps" "$RATE" "$(probe v:0 stream=r_frame_rate "$OUT")"
check "frames" "$NF" "$(count_frames "$OUT")"
# h264 with no colour description in its VUI is limited range by definition, and x264 only
# writes the range flag alongside a colour matrix, so an untagged tv input comes back "unknown"
ORANGE=$(probe v:0 stream=color_range "$OUT"); [ "$ORANGE" != "unknown" ] || ORANGE=tv
check "pix_fmt/range" "$PIX/$RANGE" "$(probe v:0 stream=pix_fmt "$OUT")/$ORANGE"
ODUR=$(probe v:0 stream=duration "$OUT")
check "video duration (ms)" "$(awk -v d="$VDUR" 'BEGIN{printf "%.0f", d*1000}')" "$(awk -v d="$ODUR" 'BEGIN{printf "%.0f", d*1000}')"
check "audio packets md5" "$(audio_md5 "$IN")" "$(audio_md5 "$OUT")"
echo "  info  container duration: in $(probe v:0 format=duration "$IN") s, out $(probe v:0 format=duration "$OUT") s"

psnr_of() { sed -n 's/.*average:\([^ ]*\).*/\1/p' | tail -1; }
P0=$("${FF[@]}" -loglevel info -i "$OUT" "${PIN[@]}" -filter_complex "[0:v]trim=end_frame=1,setpts=PTS-STARTPTS[a];[1:v]$PCHAIN[b];[a][b]psnr" -f null - 2>&1 | psnr_of)
P0IN=$("${FF[@]}" -loglevel info -i "$OUT" -i "$IN" -filter_complex "[0:v]trim=end_frame=1,setpts=PTS-STARTPTS[a];[1:v]trim=end_frame=1,setpts=PTS-STARTPTS[b];[a][b]psnr" -f null - 2>&1 | psnr_of)
# a poster that matches the old frame 0 changed nothing: fine when the film already opens
# on it (a held opening card), so say so rather than fail
if [ "$P0IN" = "inf" ] || awk -v p="$P0IN" 'BEGIN{exit !(p+0 >= 45)}'; then
  echo "  info  frame 0 vs input frame 0: PSNR $P0IN dB, the film already opens on this poster; nothing to replace"
else echo "  ok    frame 0 vs input frame 0: PSNR $P0IN dB (low = the poster replaced it)"; fi
if [ "$P0" = "inf" ] || awk -v p="$P0" 'BEGIN{exit !(p+0 >= 40)}'; then echo "  ok    frame 0 vs poster: PSNR $P0 dB"; else echo "  FAIL  frame 0 vs poster: PSNR $P0 dB (< 40)"; fail=1; fi

"${FF[@]}" -i "$OUT" -i "$IN" -filter_complex "[0:v][1:v]psnr=stats_file=$TMP/psnr.log" -f null -
read -r CNT MINP INF < <(awk '{for(i=1;i<=NF;i++) if($i ~ /^n:/){split($i,a,":"); n=a[2]} else if($i ~ /^psnr_avg:/){split($i,b,":"); v=b[2]}
  if (n>=2) {c++; if (v=="inf") inf++; else if (min=="" || v+0<min) min=v+0}} END{printf "%d %s %d\n", c, (min==""?"inf":min), inf}' "$TMP/psnr.log")
EXPECT=$((NF - 1))
check "frames 1+ compared" "$EXPECT" "$CNT"
if [ "$MINP" = "inf" ] || awk -v p="$MINP" 'BEGIN{exit !(p >= 40)}'; then
  echo "  ok    frames 1..$EXPECT vs input: min PSNR $MINP dB, $INF of $CNT bit exact (inf)"
else echo "  FAIL  frames 1..$EXPECT vs input: min PSNR $MINP dB (< 40)"; fail=1; fi

if [ "$LOSSLESS" = 1 ]; then
  md5col() { grep -v '^#' "$1" | awk -F', *' '{print $6}'; }
  "${FF[@]}" -i "$IN" -map 0:v -an -f framemd5 "$TMP/in.md5"
  "${FF[@]}" -i "$OUT" -map 0:v -an -f framemd5 "$TMP/out.md5"
  # same graph TYPE as the encode (-filter_complex): a simple -vf graph scales differently
  "${FF[@]}" "${PIN[@]}" -filter_complex "[0:v]$PCHAIN[p]" -map "[p]" -frames:v 1 -f framemd5 "$TMP/poster.md5"
  SAME=$(paste <(md5col "$TMP/in.md5") <(md5col "$TMP/out.md5") | awk 'NR>1 && $1==$2{c++} END{print c+0}')
  check "frames 1+ hash identical (lossless)" "$EXPECT" "$SAME"
  check "frame 0 hash == poster hash (lossless)" "$(md5col "$TMP/poster.md5" | head -1)" "$(md5col "$TMP/out.md5" | head -1)"
  if [ -n "$AT" ]; then
    check "poster hash == input frame $K hash (full decode)" "$(md5col "$TMP/in.md5" | sed -n "$((K + 1))p")" "$(md5col "$TMP/poster.md5" | head -1)"
  fi
fi

echo "wrote: $OUT"
echo "wrote: $PNG (upload this as the custom thumbnail where a platform allows it)"
[ "$fail" = 0 ] && echo "RESULT: PASS" || { echo "RESULT: FAIL"; exit 1; }
