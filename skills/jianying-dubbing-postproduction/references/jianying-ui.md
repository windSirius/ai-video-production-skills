# Jianying UI Notes

## App targeting

- Prefer the running app at `/Applications/VideoFusion-macOS.app` when `剪映专业版` or `com.lemon.lvpro` is ambiguous.
- Re-query after every action that changes panels, selection, or list contents.
- If Computer Use reports that the user changed the app, stop using current indexes and capture fresh state.
- Treat 「试试剪映助手」 and 「剪映助手」 as forbidden targets. Detect their labels, ancestor chain, and bounds only to avoid them; never click, open, dismiss, focus, test, or use them. If they block a required control, take a verified non-assistant route or stop. Under the production harness, every UI step also requires a fresh hit-test and one-use pre-click authorization.

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
- For a subtitle-only backup, disable `视频导出` and `音频导出`, enable `字幕导出`, select `SRT`, and confirm `Unicode / UTF-8`.
- Verify the exported file exists and parse it before changing the caption track.
- `文件 > 导入` may be media-only in Jianying builds. A successful file picker selection does not prove an SRT became a caption track.
- Use the verified route `文本 > 新建文本 > 导入本地字幕`. The file picker recognizes valid `.srt` files as `Subrip Subtitle File`.
- After confirmation, verify the filename appears under `本地字幕` as a material card. The card's existence does not place captions on the timeline.
- Drag the exact local-subtitle card into the timeline, then verify a second caption track and the imported caption count before deleting anything.
- Do not delete the original caption track until imported caption clips are visibly present and counted.

## Safe rollback

- Export SRT before destructive caption replacement.
- If deletion or import behaves unexpectedly, use Undo immediately and verify the caption track returns.
- Keep audio tracks untouched while replacing captions.
