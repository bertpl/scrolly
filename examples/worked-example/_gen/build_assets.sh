#!/usr/bin/env bash
# Generate placeholder assets for the worked-example deck.
#
# All visible assets here are first-version placeholders — simple
# colored cards with text labels. They demonstrate the asset format
# (JPG, PNG, WebP, AVIF) and slot correctly into the slides; visual
# polish is iterative.
#
# Requires ImageMagick v7 (`magick` command).
#
# Run from the repo root:
#     bash examples/worked-example/_gen/build_assets.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# Pick a sensible font (ImageMagick on macOS has no preregistered fonts).
# Override by setting FONT=/path/to/font.ttf before running.
FONT="${FONT:-/System/Library/Fonts/Helvetica.ttc}"
if [[ ! -e "${FONT}" ]]; then
    echo "error: font not found at ${FONT}" >&2
    echo "       set FONT=/path/to/font.ttf and re-run" >&2
    exit 1
fi

# --- JPG: ambient dark background for maintainer-bg slide ----------
magick -size 1600x900 gradient:'#0a0a14-#1a2a3a' \
    -quality 85 ambient-bg.jpg

# --- PNG: email-client mock for pressure slide ---------------------
magick -size 800x520 xc:white \
    -fill '#3b73d6' -draw "rectangle 0,0 800,60" \
    -font "${FONT}" -fill white -pointsize 24 -annotate +20+38 "xz-devel mailing list" \
    -fill '#222' -pointsize 20 -annotate +20+110 "Re: add a co-maintainer" \
    -fill '#888' -pointsize 14 -annotate +20+135 "Jigar Kumar  •  Apr 22, 2022" \
    -fill '#444' -pointsize 16 -annotate +20+180 "Lasse, please consider adding a co-maintainer" \
    -fill '#444' -pointsize 16 -annotate +20+205 "to xz to share the load..." \
    -fill '#222' -pointsize 20 -annotate +20+275 "Re: add a co-maintainer" \
    -fill '#888' -pointsize 14 -annotate +20+300 "Dennis Ens  •  Jun 27, 2022" \
    -fill '#444' -pointsize 16 -annotate +20+345 "+1 — Jia Tan has been very active and" \
    -fill '#444' -pointsize 16 -annotate +20+370 "should be considered for co-maintainership." \
    -fill '#222' -pointsize 20 -annotate +20+440 "Re: add a co-maintainer" \
    -fill '#888' -pointsize 14 -annotate +20+465 "Lasse Collin  •  Jun 29, 2022" \
    pressure-email.png

# --- WebP: distro logos composite for affected slide ---------------
magick -size 1200x300 xc:'#f7f8fa' \
    \( -size 200x200 xc:'#a80030' -font "${FONT}" -fill white \
       -pointsize 28 -gravity center -annotate +0+0 "Debian" \) \
       -geometry +50+50 -composite \
    \( -size 200x200 xc:'#294172' -font "${FONT}" -fill white \
       -pointsize 26 -gravity center -annotate +0+0 "Fedora" \) \
       -geometry +280+50 -composite \
    \( -size 200x200 xc:'#73ba25' -font "${FONT}" -fill white \
       -pointsize 22 -gravity center -annotate +0+0 "openSUSE" \) \
       -geometry +510+50 -composite \
    \( -size 200x200 xc:'#367bf0' -font "${FONT}" -fill white \
       -pointsize 28 -gravity center -annotate +0+0 "Kali" \) \
       -geometry +740+50 -composite \
    \( -size 200x200 xc:'#1793d1' -font "${FONT}" -fill white \
       -pointsize 28 -gravity center -annotate +0+0 "Arch" \) \
       -geometry +970+50 -composite \
    distro-logos.webp

# --- AVIF: blank-gap context cards ---------------------------------
magick -size 600x800 xc:'#e8e4d8' \
    -font "${FONT}" -fill '#5a4f3a' \
    -pointsize 48 -gravity center -annotate +0-200 "2023" \
    -pointsize 22 -annotate +0-100 "Routine maintenance" \
    -pointsize 22 -annotate +0-60 "Quiet preparation" \
    -pointsize 18 -fill '#7a6f5a' -annotate +0+180 "// nothing visibly amiss" \
    blank-card-before.avif

magick -size 600x800 xc:'#f0d4cf' \
    -font "${FONT}" -fill '#7a3a3a' \
    -pointsize 48 -gravity center -annotate +0-200 "Feb 2024" \
    -pointsize 22 -annotate +0-100 "xz 5.6.0 released" \
    -pointsize 22 -annotate +0-60 "Payload landed" \
    -pointsize 18 -fill '#a05a5a' -annotate +0+180 "// still nothing visibly amiss" \
    blank-card-after.avif

echo "regenerated:"
ls -lh ambient-bg.jpg pressure-email.png distro-logos.webp blank-card-before.avif blank-card-after.avif
