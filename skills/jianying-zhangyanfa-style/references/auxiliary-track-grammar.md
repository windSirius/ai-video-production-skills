# B/C auxiliary-track grammar

## Track responsibilities

- **A track** carries narrative continuity: complete gameplay/CG/PV footage, stable full frame, UID visible when present.
- **B track** carries evidence and clarification: books, artifacts, relic pages, quotations, maps, diagrams, approved silhouettes and short comparison cards.
- **C track** is optional emphasis: arrows, masks, relationship lines, chapter labels or one short symbolic layer. Do not create it merely because the editor supports another lane.

Use the fewest tracks that make the argument clearer. A page or silhouette that does not add evidence, identity or causal clarity should remain absent.

## Review before render

Create an index/contact sheet containing every proposed B/C asset, source path, intended time range, crop, highlight bounds, treatment and whether identity is asserted. The user reviews this pack before render. After approval, freeze asset SHA-256 values; an asset change invalidates its approval.

Character silhouettes require visible identity fidelity. Prefer approved official art or a clean mask derived from it. For an unknown Descender, an approved Traveler-back silhouette can stand in only when the card labels it as symbolic rather than a confirmed appearance.

## Evidence-page timing

- Hold dense pages for reading time; do not flash them for a frame or a few tenths of a second.
- Use true hard cuts between pages unless a specific transition is approved.
- Never set both outgoing and incoming opacity to zero at one shared cut. The empty background will flash for one or more frames.
- Every page boundary gets a `-1 / 0 / +1` frame check.

## Green-screen and alpha delivery

Choose one delivery mode before rendering:

- alpha WebM when the target editor preserves transparency correctly;
- full-frame chroma green when transparent silhouette regions are interpreted as black or the user requests green screen.

Do not place green inside a supposedly transparent subject asset. For chroma delivery, composite the approved opaque B-track artwork over a uniform key color, keep edges clean, and verify the actual key color after encoding.

## Cards and highlights

Audience cards contain only approved editorial content. Source paths, review warnings and IDs live in manifests. Derive highlight rectangles from OCR or visual pixel bounds in the original image, then apply the actual contain/pad transform. Scope coordinates to the exact card; do not reuse a global box across different images.

## Render acceptance

Check every approved asset at head/middle/tail, every page boundary, every silhouette identity, and every user-reported timecode. Confirm duration, frame rate, transparency or key color, and absence of black/green flashes. Keep the editable HTML/composition, chunk plan, asset ledger and prior accepted master.
