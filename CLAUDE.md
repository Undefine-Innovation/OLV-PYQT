# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MyLLMApp (OLV-PYQT) is a Live2D-powered PyQt5 desktop application that integrates ASR (Automatic Speech Recognition), TTS (Text-to-Speech), and LLM backends for an interactive VTuber-style chat experience. The application uses WebSocket communication between the Qt frontend and backend services.

## Development Commands

### Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Install Live2D wheel (choose based on Python version)
pip install live2d_py-0.5.3.4-cp312-cp312-win_amd64.whl  # Python 3.12
pip install live2d_py-0.5.3.4-cp311-cp311-win_amd64.whl  # Python 3.11
```

### Running
```bash
# Start the application
python main.py
```

### Testing
```bash
# Test config synchronization
python test_config_sync.py

# Test TTS player queue
python tests/test_tts_player_queue.py

# Run pytest (if configured)
python -m pytest
```

## Architecture

### Module Structure

**OQWindows/** - Qt UI layer
- `qt_window_main.py`: MainWindow with Live2DCanvas (OpenGL rendering), manages window modes (immersive/windowed/desktop pet)
- `chat_floating_window.py`: Chat interface overlay
- `qml_settings_page.py`: Settings UI using QML

**OQController/** - Business logic controllers
- `ws_controller.py`: Main WebSocket controller bridging backend and UI via Qt signals (ai_response, asr_result, expression_changed, etc.)
- `asr_recorder.py`: Audio recording and ASR integration
- `tts_player.py`: TTS audio playback with queue management
- `expression_controller.py`: Live2D expression/motion control
- `audio_state_manager.py`: Centralized audio state coordination
- `chat_history_manager.py`: Conversation history persistence

**OQConfig/** - Configuration management
- `config.yaml`: Master config with ASR/TTS/LLM provider settings and API keys
- `current_selection.json`: Active provider selection (asr, tts, llm, character_path)
- `config_manager.py`: Singleton config loader/saver
- `config_sync_service.py`: Real-time config synchronization with event system
- `app_settings_manager.py`: Application-level settings

**OQBackend/** - WebSocket client
- `ws_client.py`: Threaded WebSocket client with auto-reconnect, connects to `ws://127.0.0.1:12393/client-ws`

**OQSettings/** - Settings integration
- `settings_qml_slot.py`: QML-Python bridge for settings UI

**Resources/** - Live2D assets
- `v2/`: Live2D Cubism 2.x models (.model.json, .physics.json, expressions)
- `v3/`: Live2D Cubism 3.x models (.model3.json, .physics3.json, motions, expressions)
- Background images (RING.png, NIGHT.jpeg, etc.)

### Key Architectural Patterns

**Signal-Driven Communication**: WSController emits Qt signals (pyqtSignal) that Live2DCanvas and ChatFloatingWindow connect to for reactive updates

**Async Event Loop**: Uses `qasync.QEventLoop` to bridge PyQt5's event loop with Python's asyncio for concurrent operations

**Provider Pattern**: ASR/TTS/LLM backends are pluggable via config.yaml, supporting multiple providers:
- ASR: faster-whisper, Sherpa ONNX, Azure, Groq Whisper, FunASR
- TTS: Edge TTS, Azure TTS, Bark, Fish Audio
- LLM: OpenAI-compatible APIs (Claude, DeepSeek, OpenAI, Groq), llama-cpp-python

**WebSocket Protocol**: Backend communication follows Open-LLM-VTuber message format with typed events (transcription, synthesis, expression updates)

**Live2D Integration**: Uses `live2d.v3` Python bindings with OpenGL rendering in QOpenGLWidget, supports both Cubism 2.x and 3.x models

## Configuration

Before first run, update `OQConfig/config.yaml`:
- Set `llm_configs.*.llm_api_key` with your LLM provider API keys
- Configure TTS provider keys (Azure, etc.) if using cloud services
- Adjust `system_prompt` in `agent_config_template` for character personality

Update `OQConfig/current_selection.json` to select active providers:
- `asr`: ASR provider name (must match key in config.yaml)
- `tts`: TTS provider name
- `llm`: LLM provider name
- `character_path`: Absolute path to Live2D model file (.model3.json or .model.json)

## Important Notes

- Requires Python 3.12+ for modern async features and type hints
- OpenGL support required for Live2D rendering
- CUDA GPU recommended for local inference (faster-whisper, torch, llama-cpp-python)
- Logs written to `logs/` directory
- Chat history saved to `chat_history/` directory
- Both log directories are git-ignored and auto-managed
