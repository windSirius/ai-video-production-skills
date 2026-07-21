# VoxCPM Gradio reference

## Launch pattern

Use the user's command when provided. A common local launch is:

```bash
cd <VoxCPM-project>
source .venv/bin/activate
python app.py \
  --model-id ./pretrained_models/VoxCPM2 \
  --port 8808 \
  --device mps \
  --no-denoiser
```

Verify the service URL before opening or reloading the page. On Apple Silicon, VoxCPM2 may adjust `bfloat16` to `float32`; long segments can take several minutes.

## UI meaning

| Chinese label | English label | Meaning |
|---|---|---|
| `极致克隆模式` | `Ultimate Cloning Mode` | Use reference audio plus its transcript as a spoken prefix. |
| `参考音频内容文本（ASR 自动填充，可手动编辑）` | `Transcript of Reference Audio` | Exact words already spoken in the reference WAV. |
| `Target Text — 要合成的目标文本` | `Target Text — the content to speak` | New narration generated in the current iteration. |
| `开始生成` | `Generate Speech` | Submit the current inputs. |
| `生成结果` | `Generated Audio` | Current output; replaced by the next successful result. |

In Ultimate mode, Control Instruction is intentionally disabled.

## Saving outputs

The output control exposes a localhost URL such as:

```text
http://127.0.0.1:8808/gradio_api/file=/private/.../audio.wav
```

Capture the changed URL after each completed job and save it immediately:

```bash
curl -fsS '<url>' -o '<output-dir>/01.wav'
```

Direct saving is more reliable than clicking the Chrome download button and makes the destination explicit.

## Browser control

- Prefer Browser for a controllable in-app tab.
- If the user configured a Chrome tab manually and Browser reports no tab, use Computer Use to attach to the visible Chrome state.
- When Computer Use reports that the user changed Chrome, fetch a fresh full app state before the next action.
- Never reuse old accessibility indexes after a full state refresh.

## Common failures

- **Wrong field:** Reference transcript and Target Text were swapped. Stop the wrong job, restore the exact transcript, and resubmit the intended target.
- **Auto-ASR overwrote manual transcript:** Refill the supplied transcript and verify it before Generate.
- **Old output saved twice:** Require the generated-audio URL to change before downloading.
- **Long segment truncated:** Split at the nearest sentence or paragraph boundary and regenerate both pieces.
- **Model download or cache lock:** Avoid repeatedly toggling Ultimate mode. Inspect the running process and cache state before restarting.
- **User asks to stop:** Stop the exact app process and verify with a process listing; preserve completed WAV files.
