"""
TTS 播放模块（前端集成）
- 解码服务端下发的 Base64 音频（假定为 WAV）
- 使用 sounddevice 播放音频
- 提供队列缓冲与顺序播放，避免新音频打断当前播放
- 提供停止播放的能力（用于打断）
"""

import base64
import io
import threading
from collections import deque
from typing import Optional, Callable

import numpy as np
import sounddevice as sd
import soundfile as sf


class TTSPlayer:
    """简单的音频播放器，负责播放服务端下发的 TTS 音频。"""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = False
        self._on_started: Optional[Callable[[], None]] = None
        self._on_finished: Optional[Callable[[], None]] = None
        self._queue = deque()  # 音频片段队列（Base64字符串）
        self._lock = threading.Lock()
        self._worker_running = False

    def play_base64(self, audio_b64: str, on_started: Optional[Callable[[], None]] = None,
                    on_finished: Optional[Callable[[], None]] = None,
                    on_segment_finished: Optional[Callable[[], None]] = None) -> None:
        """
        入队并顺序播放 Base64 编码音频（假定为 WAV）。
        - on_started: 会在队列首次开始播放时触发一次
        - on_finished: 会在队列播放完毕（队列为空且未被 stop 中断）时触发一次
        - on_segment_finished: 每段音频开始播放时触发一次（用于字幕）
        """
        with self._lock:
            # 不在新片段到来时打断当前播放，改为入队顺序播放
            # 首次提供的回调在队列级别生效
            if on_started is not None and self._on_started is None:
                self._on_started = on_started
            if on_finished is not None:
                # 始终以最新的 on_finished 为队列结束回调（一般为相同信号）
                self._on_finished = on_finished
            # 入队并携带段落开始回调
            self._queue.append({
                'audio_b64': audio_b64,
                'on_segment_finished': on_segment_finished,
            })
            # 如果工作线程未运行，则启动它
            if not self._worker_running:
                self._stop_flag = False
                self._start_worker()

    def _start_worker(self) -> None:
        def _worker():
            started_emitted = False
            self._worker_running = True
            try:
                while True:
                    if self._stop_flag:
                        break

                    # 取下一段音频
                    with self._lock:
                        if not self._queue:
                            break
                        item = self._queue.popleft()
                        audio_b64 = item.get('audio_b64')

                    try:
                        # 解码 base64 到内存
                        raw = base64.b64decode(audio_b64)
                        buf = io.BytesIO(raw)

                        # 读入音频数据
                        with sf.SoundFile(buf) as f:
                            data = f.read(dtype='float32')
                            samplerate = f.samplerate

                        # 首次开始播放时触发一次开始回调
                        if not started_emitted and self._on_started:
                            try:
                                self._on_started()
                            except Exception:
                                pass
                            started_emitted = True

                        # 单段播放开始时触发 per-segment 回调（用于字幕提前显示）
                        try:
                            cb = item.get('on_segment_finished')
                            if cb:
                                cb()
                        except Exception:
                            pass

                        # 播放音频（阻塞，确保完整播放）
                        sd.play(data, samplerate=samplerate, blocking=True)
                    except Exception:
                        # 单段异常不影响后续队列；继续处理下一段
                        continue

            finally:
                try:
                    sd.stop()
                except Exception:
                    pass
                self._worker_running = False
                # 队列清空且未被 stop 主动中断，触发结束回调
                if not self._stop_flag and self._on_finished:
                    try:
                        self._on_finished()
                    except Exception:
                        pass

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止播放并清空队列（用于用户打断或显式停止）。"""
        with self._lock:
            self._stop_flag = True
            self._queue.clear()
        try:
            sd.stop()
        except Exception:
            pass
        # 工作线程会在检测到 _stop_flag 后退出