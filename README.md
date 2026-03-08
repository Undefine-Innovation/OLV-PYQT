# OLV-PYQT (Open-LLM-VTuber PyQt)

OLV-PYQT is a Live2D-powered PySide6 desktop application that integrates ASR (Automatic Speech Recognition), TTS (Text-to-Speech), and LLM backends for an interactive VTuber-style chat experience. This repository includes the Qt GUI (`OQWindows`), backend controllers (`OQController`), and configuration system (`OQConfig`) for a responsive AI character with pluggable speech, voice, and chat providers.

## Highlights
1. **Live2D-powered interface** — Qt windows render a Live2D mesh while `WSController` orchestrates transcription, synthesis, and expression updates.
2. **Extensive audio stack** — Local and cloud-first voices plus ASR (faster-whisper, Sherpa ONNX, Azure, etc.) keep streaming interactions smooth.
3. **LLM-first backend** — Flexible config-driven agent templates let you point to Claude, DeepSeek, OpenAI, Groq, or local models such as `llama-cpp-python`.

## Prerequisites
- Python 3.12+ (project requires modern async features and typed libs)
- A machine with OpenGL support for the Qt/Live2D renderer
- Optional: CUDA-enabled GPU if you plan to run `faster-whisper`, `torch`, or `llama-cpp-python` locally

## Setup
1. Create and activate a virtual environment next to this repo (`python -m venv .venv`).
2. Upgrade `pip` then install dependencies:

   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Install the correct Live2D runtime wheel that matches your interpreter (wheels are already provided for CPython 3.11/3.12).

## Configuration
- The canonical config lives in `OQConfig/config.yaml`. Before you start the app, update the `llm_configs.*.llm_api_key`, TTS key placeholders, and any Azure/Groq tokens with your own credentials.
- `OQConfig/current_selection.json` defaults to Edge TTS, Sherpa ASR, and a DeepSeek-compatible LLM. Adjust the paths (e.g., `character_path`) to point to `Resources/v3/<model>.model3.json` for your Live2D model.
- Runtime logs and histories are written out to `logs/` and `chat_history/`; those folders are ignored by Git and are cleared when appropriate.

## Running

```bash
python main.py
```

- `main.py` initializes the Qt loop, starts the Live2D canvas, and boots the WebSocket-backed controller.
- If you are building your own backend, point the controller to `ws://127.0.0.1:12393/client-ws` (see `OQController/ws_controller.py`).

## Testing

```bash
python test_config_sync.py
```

- This script verifies that the config sync service can push prompts to `OQConfig/config.yaml` and mirrors the same values back out.

## Development Notes
- Use `requirements.txt` to capture dependency versions. `pyproject.toml` already lists a subset of packages for publishing.
- Clean temporary artifacts with `git clean -fdx` only after verifying there are no unsaved changes.
- The `.gitignore` now filters `logs/`, `chat_history/`, `.venv/`, and other generated files.

## Contributing
- Fork this repo, branch from `main`, and open a pull request. Document new providers in `OQConfig/config.yaml`.
- Run `python -m pytest` (or add additional tests) before submitting.

## License

Add your preferred open-source license here (e.g., MIT, Apache 2.0, etc.).
