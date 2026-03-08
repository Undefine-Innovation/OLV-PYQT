"""
ASR 录音模块（前端集成）
- 使用 sounddevice 采集麦克风音频
- 录制固定时长的单声道 PCM 数据并封装为 WAV
- 提供回调将音频字节传递给上层（WSController）
"""

import io
import threading
import queue
import time
import io
from typing import Optional, Callable

import sounddevice as sd
import numpy as np
import soundfile as sf
from loguru import logger


class ASRRecorder:
    """
    简易录音器：固定时长采集并返回 WAV 字节
    """

    def __init__(self, samplerate: int = 16000, channels: int = 1, duration_sec: float = 5.0):
        self.samplerate = samplerate
        self.channels = channels
        self.duration_sec = duration_sec
        self._thread: Optional[threading.Thread] = None
        self._on_finished: Optional[Callable[[bytes], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._stop_flag = False

    def start(self, on_finished: Callable[[bytes], None], on_error: Optional[Callable[[str], None]] = None):
        """启动录音线程，录制固定时长并回调 WAV 字节。"""
        self._on_finished = on_finished
        self._on_error = on_error
        self._stop_flag = False

        if self._thread and self._thread.is_alive():
            logger.warning("[ASRRecorder] Recording already in progress; ignoring start()")
            return

        def run():
            try:
                logger.info(f"[ASRRecorder] Start recording: duration={self.duration_sec}s, samplerate={self.samplerate}, channels={self.channels}")
                frames_needed = int(self.duration_sec * self.samplerate)
                buffer = np.empty((frames_needed, self.channels), dtype=np.float32)

                # 录音
                recorded = sd.rec(frames_needed, samplerate=self.samplerate, channels=self.channels, dtype='float32')
                sd.wait()  # 等待录音完成

                # 写入到 WAV 内存
                mem = io.BytesIO()
                sf.write(mem, recorded, self.samplerate, format='WAV')
                wav_bytes = mem.getvalue()
                logger.info(f"[ASRRecorder] Recording finished: wav_bytes={len(wav_bytes)}")

                if self._on_finished:
                    self._on_finished(wav_bytes)
            except Exception as e:
                logger.error(f"[ASRRecorder] Recording error: {e}")
                if self._on_error:
                    try:
                        self._on_error(str(e))
                    except Exception:
                        pass

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        """预留：可扩展为打断录音（当前为固定时长）。"""
        self._stop_flag = True