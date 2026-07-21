# Jianying UI Notes

## App targeting

- Prefer the running app selected by `AI_VIDEO_EDITOR_APP` when set. Otherwise resolve the active Jianying/CapCut application by display name or bundle identifier and verify the target window before acting.
- Re-query after every action that changes panels, selection, or list contents.
- If Computer Use reports that the user changed the app, stop using current indexes and capture fresh state.

## Audio insertion

- Adding a media tile inserts at the playhead. Repeated adds at time zero create stacked tracks.
- Focus an existing timeline clip or the timeline area before pressing `End`; otherwise the key may affect the media browser.
- After every add, focus the timeline and verify the cumulative project end.

## Manuscript Match

- Route: `文本 > 智能文本 > 文稿匹配`.
- The input dialog may expose only a text area. Paste clean narration text when no file-drop target exists.
- Wait for matching to finish before styling. Successful matching creates a caption track and populates the right-side caption list.

## Caption styling

- Use the right-side `文本` tab for font, preset, and position.
- Marquee-select only the caption lane. Keep the drag box above the audio lane.
- Font selection opens a searchable dialog; verify the selected font name after closing it.
- Expand `位置大小` and scroll within the inspector when X/Y fields are off-screen.

## Caption-list editing

- Use the right-side `字幕` tab to expose editable rows.
- Rows appear as `文本栏 ... Value: ...` in accessibility state, but virtualized order may be forward, reversed, or include the focused row twice.
- Locate rows from their text and visible sequence, not from a fixed element index.
- A single text edit can invalidate every later element index. Refresh state after each edit.
- The list scrollbar is normally the last scrollbar before `MainMultiTimelineLayout`; do not assume a fixed numeric index.

## SRT export and import

- The export dialog can expose `字幕导出` below video and audio options. Scroll inside the dialog to reach it.
- Disable video export when only an SRT backup is needed.
- Verify the exported file exists and parse it before changing the caption track.
- `文件 > 导入` may be media-only in Jianying builds. A successful file picker selection does not prove an SRT became a caption track.
- Do not delete the original caption track until imported caption clips are visibly present and counted.

## Safe rollback

- Export SRT before destructive caption replacement.
- If deletion or import behaves unexpectedly, use Undo immediately and verify the caption track returns.
- Keep audio tracks untouched while replacing captions.
