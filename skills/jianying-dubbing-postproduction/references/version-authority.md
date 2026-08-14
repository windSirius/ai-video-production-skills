# Version authority for narration and captions

## Authority order

1. A final SRT that the user explicitly designates as current.
2. The canonical narration text and final audio SHA bound by the latest passing `audio_manifest.json`.
3. Canonical text fields in `segments.json`.
4. The raw Manuscript Match export.
5. ASR and pronunciation-proxy text.

Use higher layers to correct lower layers, never the reverse. ASR can expose omissions or suspicious words, but it cannot rename an official term. A synthesis proxy such as `胡寄生` remains private to generation; subtitles display `槲寄生`.

## Conflict handling

When files disagree, do not silently choose the newest modification time. Compute SHA-256, inspect the manifests, report the conflict and choose the highest-authority bound version. Keep old candidates for recovery but label them stale.

If the user supplies a new final SRT, preserve its timing and segmentation unless there is a concrete hard error. Audit lexical coverage against the canonical manuscript, then repair punctuation-only rows, forbidden terminal punctuation, duplicates, quote imbalance and true timing faults without rewriting the narration.

## Timing contract

The final audio decides the usable end time. Small differences caused by frame or millisecond rounding are acceptable within the frozen tolerance. Never stretch the entire subtitle clock to remove a few milliseconds; only real drift or a wrong audio version warrants global realignment.

## Required handoff

Keep the untouched raw match, audited semantic SRT, user-designated final SRT if different, selected audio-master hash, canonical manuscript hash, audit JSON and live-project verification note.
