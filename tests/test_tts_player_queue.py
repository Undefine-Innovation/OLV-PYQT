import base64
import io
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

from OQController.tts_player import TTSPlayer


def make_wav_b64(duration_sec=0.1, samplerate=16000):
    """生成一个短的静音 WAV（Base64）。"""
    data = np.zeros(int(duration_sec * samplerate), dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, data, samplerate=samplerate, format='WAV')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


class TestTTSPlayerQueue(unittest.TestCase):
    def test_queue_playback_triggers_started_once_and_finished_once(self):
        player = TTSPlayer()

        started_count = 0
        finished_count = 0
        finished_evt = threading.Event()

        def on_started():
            nonlocal started_count
            started_count += 1

        def on_finished():
            nonlocal finished_count
            finished_count += 1
            finished_evt.set()

        seg1 = make_wav_b64(0.05)
        seg2 = make_wav_b64(0.05)

        # 模拟 sounddevice 行为：play 立即返回；stop 为 no-op
        with patch('sounddevice.play', side_effect=lambda *args, **kwargs: None), \
             patch('sounddevice.stop', side_effect=lambda *args, **kwargs: None):
            player.play_base64(seg1, on_started=on_started, on_finished=on_finished)
            player.play_base64(seg2, on_started=on_started, on_finished=on_finished)

            # 等待队列播放结束回调
            finished_evt.wait(timeout=2.0)

        self.assertEqual(started_count, 1)
        self.assertEqual(finished_count, 1)


if __name__ == '__main__':
    unittest.main()