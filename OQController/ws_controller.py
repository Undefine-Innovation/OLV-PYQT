from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from typing import Optional, List

from OQBackend.ws_client import WebSocketClient
from OQController.asr_recorder import ASRRecorder
from OQController.tts_player import TTSPlayer
import base64
import io
import numpy as np
try:
    import soundfile as sf
except Exception:
    sf = None
from loguru import logger


DEFAULT_WS_URL = 'ws://127.0.0.1:12393/client-ws'
DEFAULT_BASE_URL = 'http://127.0.0.1:12393'


class WSController(QObject):
    """
    Qt 控制器桥接 WebSocket：
    - 提供与 ChatFloatingWindow/Live2DCanvas 兼容的信号接口
    - 在收到服务端消息时触发字幕与音频播放开始/结束等事件（骨架实现）
    """

    # 与旧 ChatController 接口保持一致的核心信号
    ai_response = pyqtSignal(str)
    asr_result = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    recording_started = pyqtSignal()
    recording_finished = pyqtSignal()
    transcription_started = pyqtSignal()
    transcription_finished = pyqtSignal(str)
    expression_changed = pyqtSignal(list)

    # Live2D/字幕相关信号
    audio_playback_started = pyqtSignal()
    audio_playback_finished = pyqtSignal()
    subtitle_display_requested = pyqtSignal(str, int)
    subtitle_clear_requested = pyqtSignal(int)

    # 连接状态
    ws_state_changed = pyqtSignal(str)

    # History signals
    history_list_received = pyqtSignal(list)
    history_data_received = pyqtSignal(list)
    history_created = pyqtSignal(str)
    history_deleted = pyqtSignal(bool)

    def __init__(self, ws_url: Optional[str] = None, base_url: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.ws_url = ws_url or DEFAULT_WS_URL
        self.base_url = base_url or DEFAULT_BASE_URL
        self._client: Optional[WebSocketClient] = None
        self._subtitle_seq = 0
        self._history_uid: Optional[str] = None
        self._current_subtitle_seq: Optional[int] = None

        # 前端 ASR/TTS 模块
        self._asr = ASRRecorder()
        self._tts = TTSPlayer()
        
        # 记录后端合成完成标记，用于播放结束后回传完成信号
        self._backend_synth_complete: bool = False

    # --- 对外方法 ---
    def connect_ws(self):
        logger.info(f"[WSController] Connecting to {self.ws_url}")
        self._client = WebSocketClient(self.ws_url)
        self._client.set_on_state(self._on_state)
        self._client.set_on_message(self._on_message)
        self._client.connect()

    def disconnect_ws(self):
        if self._client:
            logger.info("[WSController] Disconnecting WS client")
            self._client.close()
            self._client = None

    def on_text_sent(self, text: str):
        """供 ChatFloatingWindow 调用，发送文本输入。"""
        if not text:
            return
        if self._client:
            self._client.send_message({
                'type': 'text-input',
                'text': text,
                # images 字段留空，未来可接入截屏等
            })
            logger.info(f"[WSController] Text sent, len={len(text)}")
            self.status_updated.emit('已发送文本')

    def on_voice_record_request(self):
        """触发一次固定时长的语音录制，并将音频发送给后端进行转写。"""
        logger.info("[WSController] Voice record requested")
        # 先检查WS连接状态，避免静默失败
        if not self._client or not self._client.is_open():
            logger.error("[WSController] WS not open, cannot start ASR recording")
            self.error_occurred.emit('未连接后端，无法开始语音识别')
            self.status_updated.emit('请检查WS服务是否运行或连接设置')
            return

        # 录音开始
        self.recording_started.emit()
        self.status_updated.emit('正在录音...')
        logger.info("[WSController] Recording started")

        def _on_finished(wav_bytes: bytes):
            # 录音结束
            self.recording_finished.emit()
            self.status_updated.emit('录音完成，开始提交识别')
            logger.info(f"[WSController] Recording finished, wav_bytes={len(wav_bytes)}")

            # 通知 UI：进入转写阶段
            self.transcription_started.emit()

            # 发送到后端：按 Web 前端协议改为 mic-audio-data/mic-audio-end
            if not self._client or not self._client.is_open():
                logger.error("[WSController] WS disconnected during recording; audio not submitted")
                self.error_occurred.emit('连接断开，语音未提交')
                self.status_updated.emit('请重连后重试')
                return

            floats: list[float] = []
            try:
                if sf is not None:
                    with sf.SoundFile(io.BytesIO(wav_bytes)) as f:
                        data = f.read(dtype='float32')
                        floats = data.tolist()
                else:
                    import wave
                    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
                        frames = wf.readframes(wf.getnframes())
                        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                        floats = data.tolist()
            except Exception as e:
                logger.error(f"[WSController] Failed to decode WAV to float32: {e}")
                self.error_occurred.emit('音频解码失败，未提交到后端')
                return

            # 分片发送并结束
            self._submit_mic_audio_float32(floats)
            self.status_updated.emit('已提交语音到后端')

        def _on_error(err_msg: str):
            # 录音过程失败（设备/驱动/库异常）
            self.recording_finished.emit()
            self.error_occurred.emit(f'录音失败：{err_msg}')
            self.status_updated.emit('录音失败，请检查麦克风权限、设备或音频库安装')
            logger.error(f"[WSController] Recording error: {err_msg}")

        # 开始录音（固定时长）
        try:
            self._asr.start(_on_finished, on_error=_on_error)
        except Exception as e:
            logger.error(f"[WSController] Failed to start recording: {e}")
            self.error_occurred.emit('启动录音失败')

    # --- 内部事件 ---
    def _on_state(self, state: str):
        self.ws_state_changed.emit(state)
        logger.info(f"[WSController] WS state: {state}")
        if state == 'CLOSED':
            self.status_updated.emit('连接已关闭')
        elif state == 'OPEN':
            self.status_updated.emit('连接已建立')
        elif state == 'CONNECTING':
            self.status_updated.emit('正在连接...')
        elif state == 'ERROR':
            self.error_occurred.emit('WebSocket 连接错误')

    def _on_message(self, message: dict):
        msg_type = message.get('type')
        logger.debug(f"[WSController] Received message type={msg_type}")

        # 文本字幕（完整文本）
        if msg_type == 'full-text':
            text = message.get('text') or ''
            # 不直接显示整段字幕，避免覆盖逐句显示
            return

        # 音频消息（用于嘴巴控制与字幕）
        if msg_type == 'audio':
            # 先取音频片段以评估时长
            audio_b64 = message.get('audio') or ''
            logger.info(f"[WSController] Received audio segment, b64_len={len(audio_b64)}")

            # 提取显示文本，但仅在对应音频片段播放结束后再显示
            display_text = message.get('display_text') or {}
            text = display_text.get('text') or ''

            # 表情动作（如有）
            actions = message.get('actions') or {}
            expressions = actions.get('expressions')
            if expressions is not None:
                try:
                    self.expression_changed.emit(list(expressions))
                except Exception:
                    pass

            # 播放 TTS 音频
            if audio_b64:
                self._tts.play_base64(
                    audio_b64,
                    on_started=lambda: self.audio_playback_started.emit(),
                    on_finished=self._on_audio_playback_finished,
                    on_segment_finished=(lambda t=text: self._on_tts_segment_finished(t)) if text else None,
                )
            return

        # 用户语音输入的转写结果
        if msg_type == 'user-input-transcription':
            text = message.get('text') or ''
            if text:
                self.asr_result.emit(text)
                self.transcription_finished.emit(text)
                logger.info(f"[WSController] Transcription: {text[:80]}{'...' if len(text) > 80 else ''}")
            else:
                self.transcription_finished.emit('')
                logger.info("[WSController] Transcription: <empty>")
            return

        # 历史数据
        if msg_type == 'history-data':
            messages = message.get('messages') or []
            try:
                self.history_data_received.emit(messages)
            except Exception as e:
                logger.error(f"[WSController] 发射历史数据信号失败: {e}")
            return

        # 历史列表
        if msg_type == 'history-list':
            histories = message.get('histories') or []
            if histories:
                try:
                    self._history_uid = histories[0].get('uid')
                except Exception:
                    self._history_uid = None
            try:
                self.history_list_received.emit(histories)
            except Exception as e:
                logger.error(f"[WSController] 发射历史列表信号失败: {e}")
            return

        # 新历史创建完成
        if msg_type == 'new-history-created':
            uid = message.get('history_uid')
            if uid:
                self._history_uid = uid
                try:
                    self.history_created.emit(uid)
                except Exception as e:
                    logger.error(f"[WSController] 发射新历史信号失败: {e}")
            return

        # 历史删除结果
        if msg_type == 'history-deleted':
            success = bool(message.get('success'))
            try:
                self.history_deleted.emit(success)
            except Exception as e:
                logger.error(f"[WSController] 发射历史删除信号失败: {e}")
            return

        # 后端通知：合成完成（等待前端播放队列结束后再回传完成）
        if msg_type == 'backend-synth-complete':
            self._backend_synth_complete = True
            return

        # 其他控制类消息（可根据需要扩展）
        if msg_type == 'control':
            text = message.get('text') or ''
            if text:
                # 映射部分控制提示到状态
                if text == 'conversation-chain-start':
                    self.status_updated.emit('对话开始')
                elif text == 'conversation-chain-end':
                    self.status_updated.emit('对话结束')
                elif text == 'start-mic':
                    self.status_updated.emit('开启麦克风')
                elif text == 'stop-mic':
                    self.status_updated.emit('关闭麦克风')
                else:
                    self.status_updated.emit(f'控制消息：{text}')
            return

        # 错误消息
        if msg_type == 'error':
            err = message.get('message') or '后端错误'
            self.error_occurred.emit(err)
            logger.error(f"[WSController] Backend error: {err}")
            return

        # 兜底：未识别消息类型
        # 保持沉默以避免过多日志，但保留可扩展点
        return

    def _get_audio_duration_ms(self, audio_b64: str) -> int:
        """从 Base64 WAV 数据推断音频时长（毫秒），失败时返回默认1500ms。"""
        try:
            if not audio_b64:
                return 1500
            raw = base64.b64decode(audio_b64)
            if sf is None:
                return 1500
            with sf.SoundFile(io.BytesIO(raw)) as f:
                frames = len(f)
                samplerate = f.samplerate or 16000
                if samplerate <= 0:
                    samplerate = 16000
                duration_sec = frames / float(samplerate)
                return int(duration_sec * 1000) + 100
        except Exception:
            return 1500

    def _on_tts_segment_finished(self, text: str) -> None:
        """每段 TTS 音频播放结束后再显示对应字幕。"""
        try:
            if not text:
                return
            self._subtitle_seq += 1
            seq_id = self._subtitle_seq
            self._current_subtitle_seq = seq_id
            self.subtitle_display_requested.emit(text, seq_id)
        except Exception:
            # 安静失败，避免影响后续片段
            pass

    def _maybe_clear_subtitle(self, seq_id: int) -> None:
        """仅当待清除序号仍为当前字幕时执行清除。"""
        if self._current_subtitle_seq == seq_id:
            try:
                self.subtitle_clear_requested.emit(seq_id)
            except Exception:
                pass
            self._current_subtitle_seq = None

    # 外部可调用：停止 TTS 并发送打断
    def stop_tts_playback_and_interrupt(self):
        try:
            self._tts.stop()
        except Exception:
            pass
        # 主动打断时清理当前字幕
        if self._current_subtitle_seq is not None:
            try:
                self.subtitle_clear_requested.emit(self._current_subtitle_seq)
            except Exception:
                pass
            self._current_subtitle_seq = None
        if self._client:
            try:
                self._client.send_message({'type': 'interrupt-signal', 'text': ''})
                logger.info("[WSController] Sent interrupt-signal to backend and stopped TTS")
            except Exception:
                pass

    # 供自动语音识别（VAD）路径直接提交音频字节
    def send_audio_bytes(self, audio_bytes: bytes):
        try:
            # 先检查WS连接状态
            if not self._client or not self._client.is_open():
                self.error_occurred.emit('未连接后端，无法提交自动识别音频')
                self.status_updated.emit('请检查WS服务是否运行或连接设置')
                logger.error("[WSController] WS not open, cannot submit VAD audio")
                return

            self.transcription_started.emit()
            logger.info(f"[WSController] Submitting VAD audio, bytes={len(audio_bytes)}")

            # 改为发送 mic-audio-data 浮点数组分片 + mic-audio-end
            data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            self._submit_mic_audio_float32(data.tolist())
            self.status_updated.emit('已提交自动识别音频到后端')
        except Exception as e:
            logger.error(f"[WSController] Failed to submit VAD audio: {e}")
            self.error_occurred.emit('提交自动识别音频失败')

    def _on_audio_playback_finished(self):
        """整队列播放结束后，回传前端播放完成以推进对话链。"""
        try:
            self.audio_playback_finished.emit()
        except Exception:
            pass
        try:
            if self._backend_synth_complete and self._client and self._client.is_open():
                self._client.send_message({'type': 'frontend-playback-complete'})
                self._backend_synth_complete = False
                logger.info("[WSController] Sent frontend-playback-complete after playback")
        except Exception as e:
            logger.error(f"[WSController] Failed to send frontend-playback-complete: {e}")

    def _submit_mic_audio_float32(self, floats: list[float]):
        """按 Web 前端协议发送麦克风音频：4096 分片 + 结束信号。"""
        try:
            chunk_size = 4096
            # 分片发送音频数据
            for i in range(0, len(floats), chunk_size):
                chunk = floats[i:i + chunk_size]
                payload = {
                    'type': 'mic-audio-data',
                    'audio': chunk,
                }
                if self._history_uid:
                    payload['history_uid'] = self._history_uid
                self._client.send_message(payload)

            # 发送结束信号（可附带当前历史）
            end_payload = {'type': 'mic-audio-end'}
            if self._history_uid:
                end_payload['history_uid'] = self._history_uid
            self._client.send_message(end_payload)
            logger.info(f"[WSController] Sent mic-audio-end, chunks={max(1, (len(floats)+chunk_size-1)//chunk_size)}")
        except Exception as e:
            logger.error(f"[WSController] Failed to send mic audio: {e}")
            self.error_occurred.emit('发送麦克风音频失败')

    # --- History request helpers ---
    def request_history_list(self):
        if self._client and self._client.is_open():
            self._client.send_message({'type': 'fetch-history-list'})
        else:
            logger.debug('[WSController] WS未连接，无法请求历史列表')

    def request_create_new_history(self):
        if self._client and self._client.is_open():
            self._client.send_message({'type': 'create-new-history'})
        else:
            logger.debug('[WSController] WS未连接，无法创建新历史')

    def request_fetch_and_set_history(self, history_uid: str):
        if not history_uid:
            return
        if self._client and self._client.is_open():
            self._client.send_message({'type': 'fetch-and-set-history', 'history_uid': history_uid})
        else:
            logger.debug('[WSController] WS未连接，无法请求历史数据')

    def request_delete_history(self, history_uid: str):
        if not history_uid:
            return
        if self._client and self._client.is_open():
            self._client.send_message({'type': 'delete-history', 'history_uid': history_uid})
        else:
            logger.debug('[WSController] WS未连接，无法删除历史')