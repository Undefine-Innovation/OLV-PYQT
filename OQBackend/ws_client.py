import json
import threading
import time
from typing import Callable, Optional, Any, Dict, List
from loguru import logger

try:
    import websocket  # websocket-client
except Exception as e:
    websocket = None
    logger.warning(f"[WS] 未找到 websocket-client 库: {e}")


class WebSocketClient:
    """
    轻量级 WebSocket 客户端，实现与后端的真实连接：
    - 提供 connect / close / send_message / set_on_message / set_on_state
    - 线程化运行，支持自动重连与心跳
    - 遵循 Open-LLM-VTuber 文档定义的消息类型（透明转发）
    """

    def __init__(self, url: str, headers: Optional[List[str]] = None):
        self.url = url
        self.headers = headers or []
        self._on_message: Optional[Callable[[Dict[str, Any]], None]] = None
        self._on_state: Optional[Callable[[str], None]] = None
        self._state = 'CLOSED'
        self._worker: Optional[threading.Thread] = None
        self._running = False
        self._ws_app: Optional["websocket.WebSocketApp"] = None
        self._reconnect_backoff = 1.0

    # --- 回调设置 ---
    def set_on_message(self, cb: Callable[[Dict[str, Any]], None]):
        self._on_message = cb

    def set_on_state(self, cb: Callable[[str], None]):
        self._on_state = cb

    # --- 连接状态查询 ---
    def is_open(self) -> bool:
        """当前WS是否已建立连接。"""
        return self._state == 'OPEN'

    def get_state(self) -> str:
        """返回当前连接状态：CONNECTING/OPEN/CLOSED/ERROR。"""
        return self._state

    # --- 连接管理 ---
    def connect(self):
        """启动真实连接线程。"""
        if self._state == 'OPEN' or self._running:
            return
        if websocket is None:
            logger.error("[WS] 依赖 websocket-client 未安装，无法建立连接")
            self._set_state('ERROR')
            return

        self._set_state('CONNECTING')
        self._running = True
        self._worker = threading.Thread(target=self._run_loop, daemon=True)
        self._worker.start()

    def _run_loop(self):
        """循环运行，断线自动重连。"""
        while self._running:
            try:
                self._ws_app = websocket.WebSocketApp(
                    self.url,
                    header=self.headers,
                    on_open=self._on_open,
                    on_message=self._on_message_ws,
                    on_error=self._on_error_ws,
                    on_close=self._on_close_ws,
                )
                # 心跳与重连由外层控制；run_forever在关闭后返回
                self._ws_app.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logger.error(f"[WS] 运行错误: {e}")
                self._set_state('ERROR')

            if not self._running:
                break

            # 退避重连
            wait = min(self._reconnect_backoff, 10.0)
            logger.info(f"[WS] 断线重连，{wait:.1f}s 后尝试连接")
            time.sleep(wait)
            self._reconnect_backoff = min(self._reconnect_backoff * 2.0, 10.0)

    def close(self):
        """关闭连接并停止线程。"""
        self._running = False
        try:
            if self._ws_app:
                self._ws_app.close()
        except Exception as e:
            logger.warning(f"[WS] 关闭时出错: {e}")
        self._set_state('CLOSED')

    # --- 事件回调 ---
    def _on_open(self, ws):
        logger.info(f"[WS] 已连接到 {self.url}")
        self._reconnect_backoff = 1.0
        self._set_state('OPEN')

        # 初始握手消息（可选，对齐文档）
        self._send_json({'type': 'fetch-configs'})
        self._send_json({'type': 'fetch-backgrounds'})
        self._send_json({'type': 'fetch-history-list'})
        self._send_json({'type': 'create-new-history'})

    def _on_message_ws(self, ws, message: str):
        try:
            data = json.loads(message)
        except Exception:
            # 一些服务端可能发送非JSON心跳或文本
            logger.debug(f"[WS] 收到非JSON消息: {message[:200]}")
            return

        if self._on_message:
            try:
                self._on_message(data)
            except Exception as e:
                logger.error(f"[WS] on_message 回调错误: {e}")

    def _on_error_ws(self, ws, error):
        logger.error(f"[WS] 连接错误: {error}")
        self._set_state('ERROR')

    def _on_close_ws(self, ws, status_code, msg):
        logger.info(f"[WS] 连接关闭: code={status_code}, msg={msg}")
        self._set_state('CLOSED')

    def _set_state(self, state: str):
        self._state = state
        if self._on_state:
            try:
                self._on_state(state)
            except Exception as e:
                logger.error(f"[WS] on_state 回调错误: {e}")

    # --- 发送消息 ---
    def _send_json(self, payload: Dict[str, Any]):
        try:
            if self._ws_app and self._state == 'OPEN':
                self._ws_app.send(json.dumps(payload))
            else:
                logger.debug("[WS] 连接未就绪，跳过发送")
        except Exception as e:
            logger.error(f"[WS] 发送失败: {e}")

    def send_message(self, message: Dict[str, Any]):
        """发送 JSON 格式消息到后端。"""
        self._send_json(message)