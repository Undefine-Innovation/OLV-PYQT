from PySide6.QtCore import Qt, QEvent, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QPushButton, QApplication,
    QHBoxLayout, QScrollArea, QTextEdit, QFrame, QComboBox, QInputDialog, QSlider
)
import pyaudio
import torch
import numpy as np
import io
import soundfile as sf
import threading
import time
import logging

# 导入聊天历史管理器
from OQController.chat_history_manager import get_history, store_message, create_new_history, get_history_list


class ChatFloatingWindow(QWidget):
    """悬浮聊天窗口 - 增强版，支持语音交互"""

    # 定义信号
    window_closed = Signal()
    message_sent = Signal(str)
    voice_record_requested = Signal()  # 新增：语音录音请求信号

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.dragging = False
        self.parent_window = parent
        self.controller = controller  # 聊天控制器

        # 聊天数据
        self.chat_messages = []
        self.conf_uid = "default"  # 默认配置ID
        self.history_uid = "current"  # 当前会话ID

        # VAD相关属性
        self.vad_active = False
        self.vad_thread = None
        self.vad_audio_stream = None
        self.vad_silence_timer = None
        self.vad_audio_buffer = []
        self.vad_recording = False
        self.last_speech_time = 0
        self.vad_start_time = 0
        # AI说话期间暂停VAD的标志
        self.vad_paused_by_ai = False

        # 配置日志
        self.logger = logging.getLogger('VAD_System')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        # 初始化UI和窗口属性
        self.setup_controller_connections()
        self.setup_window_properties()
        self.setup_ui()

        # 加载聊天室
        self.load_chat_rooms()

        # 安装事件过滤器
        self.input_text.installEventFilter(self)

    def setup_controller_connections(self):
        """设置控制器信号连接"""
        if not self.controller:
            return

        # 连接发送信号到控制器
        self.message_sent.connect(self.controller.on_text_sent)
        self.voice_record_requested.connect(self.controller.on_voice_record_request)

        # 连接控制器回复信号
        self.controller.ai_response.connect(self.add_ai_response)
        self.controller.asr_result.connect(self.add_voice_message)
        self.controller.status_updated.connect(self.update_status)
        self.controller.error_occurred.connect(self.show_error)

        # 字幕显示信号
        if hasattr(self.controller, 'subtitle_display_requested'):
            try:
                self.controller.subtitle_display_requested.connect(self.on_subtitle_display_requested)
            except Exception:
                pass

        # AI语音开始/结束
        if hasattr(self.controller, 'audio_playback_started'):
            try:
                self.controller.audio_playback_started.connect(self.on_ai_audio_started)
            except Exception:
                pass
        if hasattr(self.controller, 'audio_playback_finished'):
            try:
                self.controller.audio_playback_finished.connect(self.on_ai_audio_finished)
            except Exception:
                pass

        # 连接录音状态信号
        self.controller.recording_started.connect(self.on_recording_started)
        self.controller.recording_finished.connect(self.on_recording_finished)
        self.controller.transcription_started.connect(self.on_transcription_started)
        self.controller.transcription_finished.connect(self.on_transcription_finished)

        # 历史记录相关信号
        if hasattr(self.controller, 'history_list_received'):
            self.controller.history_list_received.connect(self.on_history_list_received)
        if hasattr(self.controller, 'history_data_received'):
            self.controller.history_data_received.connect(self.on_history_data_received)
        if hasattr(self.controller, 'history_created'):
            self.controller.history_created.connect(self.on_new_history_created)
        if hasattr(self.controller, 'history_deleted'):
            self.controller.history_deleted.connect(self.on_history_deleted)

    def setup_window_properties(self):
        """设置窗口属性"""
        self.setWindowTitle("AI语音聊天")
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(215, 650)

        # 设置初始位置（屏幕右侧）
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 470, 50)

    def setup_ui(self):
        """设置UI界面"""
        # 主容器
        main_container = QFrame(self)
        main_container.setObjectName("mainContainer")
        main_container.setStyleSheet("""
            QFrame#mainContainer {
                background-color: rgba(18, 20, 30, 245);
                border-radius: 18px;
                border: 1px solid rgba(90, 100, 130, 120);
            }
        """)

        # 主布局
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 标题栏
        title_bar = self.create_title_bar()
        main_layout.addWidget(title_bar)

        # 聊天室选择区域
        chat_room_area = self.create_chat_room_selector()
        main_layout.addWidget(chat_room_area)

        # 聊天内容区域
        self.chat_area = self.create_chat_area()
        main_layout.addWidget(self.chat_area, 1)

        # 输入区域（包含语音按钮）
        input_area = self.create_input_area()
        main_layout.addWidget(input_area)

        # 状态栏
        status_bar = self.create_status_bar()
        main_layout.addWidget(status_bar)

        # 设置主容器布局
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(main_container)

    def create_title_bar(self):
        """创建标题栏"""
        title_frame = QFrame()
        title_frame.setObjectName("titleBar")
        title_frame.setStyleSheet("""
            QFrame#titleBar {
                background-color: rgba(255, 255, 255, 0.03);
                border-radius: 14px;
                border: 1px solid rgba(100, 110, 140, 60);
            }
        """)
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(8, 6, 8, 6)
        title_layout.setSpacing(6)

        # 标题
        title_label = QLabel("🎤 AI语音聊天")
        title_label.setStyleSheet("""
            QLabel {
                color: rgba(238, 240, 248, 255);
                font-size: 12px;
                font-weight: 700;
                padding: 2px 4px;
                background: transparent;
                border: none;
            }
        """)

        # 最小化按钮
        minimize_btn = QPushButton("−")
        minimize_btn.setFixedSize(24, 24)
        minimize_btn.setCursor(Qt.PointingHandCursor)
        minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(90, 95, 120, 140);
                border-radius: 8px;
                color: rgba(235, 238, 245, 255);
                font-size: 12px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(110, 118, 145, 180);
            }
            QPushButton:pressed {
                background-color: rgba(75, 82, 105, 180);
            }
        """)
        minimize_btn.clicked.connect(self.showMinimized)

        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(190, 75, 75, 180);
                border-radius: 8px;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(215, 95, 95, 210);
            }
            QPushButton:pressed {
                background-color: rgba(160, 58, 58, 200);
            }
        """)
        close_btn.clicked.connect(self.close_window)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(minimize_btn)
        title_layout.addWidget(close_btn)

        return title_frame

    def create_chat_room_selector(self):
        """创建聊天室选择区域"""
        selector_frame = QFrame()
        selector_frame.setObjectName("selectorFrame")
        selector_frame.setStyleSheet("""
            QFrame#selectorFrame {
                background-color: rgba(32, 35, 48, 220);
                border-radius: 14px;
                border: 1px solid rgba(92, 104, 140, 90);
            }
        """)

        selector_layout = QHBoxLayout(selector_frame)
        selector_layout.setContentsMargins(12, 10, 12, 10)
        selector_layout.setSpacing(10)

        # 聊天室标签
        room_label = QLabel("聊天室:")
        room_label.setStyleSheet("""
            QLabel {
                color: rgba(226, 228, 235, 255);
                font-size: 12px;
                font-weight: 700;
                background: transparent;
                border: none;
            }
        """)

        # 聊天室下拉选择框
        self.room_selector = QComboBox()
        self.room_selector.setMinimumHeight(40)
        self.room_selector.setMinimumWidth(180)
        self.room_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(45, 49, 66, 235);
                border: 1px solid rgba(96, 110, 150, 110);
                border-radius: 10px;
                color: rgba(235, 237, 244, 255);
                font-size: 12px;
                padding: 0 12px;
            }
            QComboBox:hover {
                border: 1px solid rgba(110, 150, 225, 180);
            }
            QComboBox:focus {
                border: 2px solid rgba(100, 150, 220, 180);
            }
            QComboBox::drop-down {
                border: none;
                width: 26px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid rgba(230, 233, 240, 255);
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(43, 47, 62, 245);
                border: 1px solid rgba(96, 110, 150, 110);
                border-radius: 10px;
                color: rgba(235, 237, 244, 255);
                selection-background-color: rgba(82, 132, 208, 180);
                outline: none;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 6px 10px;
                border-radius: 6px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: rgba(82, 132, 208, 110);
            }
        """)
        self.room_selector.currentTextChanged.connect(self.switch_chat_room)

        # 新建聊天室按钮
        new_room_btn = QPushButton("+")
        new_room_btn.setFixedSize(40, 40)
        new_room_btn.setCursor(Qt.PointingHandCursor)
        new_room_btn.setToolTip("创建新聊天室")
        new_room_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(77, 144, 215, 190);
                border: none;
                border-radius: 20px;
                color: white;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(95, 161, 230, 220);
            }
            QPushButton:pressed {
                background-color: rgba(63, 127, 194, 210);
            }
        """)
        new_room_btn.clicked.connect(self.create_new_chat_room)

        selector_layout.addWidget(room_label)
        selector_layout.addWidget(self.room_selector, 1)
        selector_layout.addWidget(new_room_btn)

        return selector_frame

    def create_chat_area(self):
        """创建聊天内容区域"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid rgba(90, 100, 130, 70);
                border-radius: 14px;
                background-color: rgba(20, 22, 32, 160);
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background-color: rgba(60, 64, 82, 90);
                width: 8px;
                border-radius: 4px;
                margin: 6px 2px 6px 2px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(122, 129, 155, 170);
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(145, 152, 180, 200);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

        # 聊天内容容器
        self.chat_content = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setContentsMargins(10, 10, 10, 10)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()

        scroll_area.setWidget(self.chat_content)
        return scroll_area

    def create_input_area(self):
        """创建输入区域（修复间距 + 优化视觉层次）"""
        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_frame.setStyleSheet("""
            QFrame#inputFrame {
                background-color: rgba(28, 31, 44, 235);
                border-radius: 16px;
                border: 1px solid rgba(95, 108, 145, 95);
            }
        """)

        input_layout = QVBoxLayout(input_frame)
        # 这里是重点修复：明确设置内容边距和上下间隔，避免控件贴边/按钮行过于松散
        input_layout.setContentsMargins(12, 12, 12, 12)
        input_layout.setSpacing(10)

        # 文本输入行
        text_input_layout = QHBoxLayout()
        text_input_layout.setContentsMargins(0, 0, 0, 0)
        text_input_layout.setSpacing(8)

        # 输入框
        self.input_text = QTextEdit()
        self.input_text.setMinimumHeight(44)
        self.input_text.setMaximumHeight(44)
        self.input_text.setPlaceholderText("输入消息...")
        self.input_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.input_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(44, 47, 61, 235);
                border: 1px solid rgba(96, 110, 150, 110);
                border-radius: 6px;
                color: rgba(235, 237, 244, 255);
                font-size: 12px;
                padding: 10px 12px;
                selection-background-color: rgba(92, 144, 220, 170);
            }
            QTextEdit:focus {
                border: 2px solid rgba(100, 150, 220, 180);
            }
        """)

        # 绑定回车键发送
        self.input_text.installEventFilter(self)

        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedWidth(96)
        self.send_btn.setMinimumHeight(44)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(77, 144, 215, 205);
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 16px;
                font-weight: 700;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: rgba(95, 161, 230, 225);
            }
            QPushButton:pressed {
                background-color: rgba(63, 127, 194, 220);
            }
            QPushButton:disabled {
                background-color: rgba(80, 86, 104, 130);
                color: rgba(160, 165, 180, 180);
            }
        """)
        self.send_btn.clicked.connect(self.send_message)

        text_input_layout.addWidget(self.input_text, 1)
        text_input_layout.addWidget(self.send_btn)

        # 语音按钮行
        voice_layout = QHBoxLayout()
        voice_layout.setContentsMargins(0, 2, 0, 0)
        voice_layout.setSpacing(8)

        # 自动语音识别按钮
        self.auto_voice_btn = QPushButton("🎯 自动识别")
        self.auto_voice_btn.setMinimumHeight(22)
        self.auto_voice_btn.setCursor(Qt.PointingHandCursor)
        self.auto_voice_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(86, 156, 92, 210);
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: rgba(100, 175, 106, 230);
            }
            QPushButton:pressed {
                background-color: rgba(72, 140, 79, 220);
            }
            QPushButton:disabled {
                background-color: rgba(80, 86, 104, 130);
                color: rgba(160, 165, 180, 180);
            }
        """)
        self.auto_voice_btn.clicked.connect(self.toggle_auto_voice_recognition)

        # 语音录制按钮
        self.voice_btn = QPushButton("🎤 语音输入")
        self.voice_btn.setMinimumHeight(22)
        self.voice_btn.setCursor(Qt.PointingHandCursor)
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(196, 90, 90, 210);
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: rgba(216, 110, 110, 230);
            }
            QPushButton:pressed {
                background-color: rgba(176, 74, 74, 220);
            }
            QPushButton:disabled {
                background-color: rgba(80, 86, 104, 130);
                color: rgba(160, 165, 180, 180);
            }
        """)
        self.voice_btn.clicked.connect(self.start_voice_input)

        voice_layout.addWidget(self.auto_voice_btn, 1)
        voice_layout.addWidget(self.voice_btn, 1)

        input_layout.addLayout(text_input_layout)
        input_layout.addLayout(voice_layout)

        return input_frame

    def create_character_control_area(self):
        """创建人物控制面板"""
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(35, 35, 45, 180);
                border-radius: 10px;
                border: 1px solid rgba(80, 80, 100, 100);
            }
        """)

        control_layout = QVBoxLayout(control_frame)
        control_layout.setContentsMargins(10, 8, 10, 8)
        control_layout.setSpacing(8)

        # 标题
        title_label = QLabel("🎭 人物控制")
        title_label.setStyleSheet("""
            QLabel {
                color: rgba(220, 220, 230, 255);
                font-size: 12px;
                font-weight: bold;
                padding: 2px;
            }
        """)
        control_layout.addWidget(title_label)

        # 缩放控制
        scale_layout = QHBoxLayout()
        scale_label = QLabel("缩放:")
        scale_label.setStyleSheet("""
            QLabel {
                color: rgba(200, 200, 210, 255);
                font-size: 12px;
                min-width: 40px;
            }
        """)

        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setMinimum(50)  # 最小50%
        self.scale_slider.setMaximum(200)  # 最大200%
        self.scale_slider.setValue(100)  # 默认100%
        self.scale_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid rgba(80, 80, 100, 120);
                height: 6px;
                background: rgba(45, 45, 55, 200);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: rgba(70, 130, 180, 180);
                border: 1px solid rgba(100, 150, 200, 180);
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: rgba(90, 150, 200, 200);
            }
        """)

        self.scale_value_label = QLabel("100%")
        self.scale_value_label.setStyleSheet("""
            QLabel {
                color: rgba(200, 200, 210, 255);
                font-size: 12px;
                min-width: 35px;
            }
        """)

        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.scale_value_label)
        control_layout.addLayout(scale_layout)

        # X轴位置控制
        x_pos_layout = QHBoxLayout()
        x_pos_label = QLabel("左右:")
        x_pos_label.setStyleSheet("""
            QLabel {
                color: rgba(200, 200, 210, 255);
                font-size: 12px;
                min-width: 40px;
            }
        """)

        self.x_pos_slider = QSlider(Qt.Horizontal)
        self.x_pos_slider.setMinimum(-100)
        self.x_pos_slider.setMaximum(100)
        self.x_pos_slider.setValue(0)
        self.x_pos_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid rgba(80, 80, 100, 120);
                height: 6px;
                background: rgba(45, 45, 55, 200);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: rgba(120, 180, 70, 180);
                border: 1px solid rgba(150, 200, 100, 180);
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: rgba(140, 200, 90, 200);
            }
        """)

        self.x_pos_value_label = QLabel("0")
        self.x_pos_value_label.setStyleSheet("""
            QLabel {
                color: rgba(200, 200, 210, 255);
                font-size: 12px;
                min-width: 35px;
            }
        """)

        x_pos_layout.addWidget(x_pos_label)
        x_pos_layout.addWidget(self.x_pos_slider)
        x_pos_layout.addWidget(self.x_pos_value_label)
        control_layout.addLayout(x_pos_layout)

        # Y轴位置控制
        y_pos_layout = QHBoxLayout()
        y_pos_label = QLabel("上下:")
        y_pos_label.setStyleSheet("""
            QLabel {
                color: rgba(200, 200, 210, 255);
                font-size: 12px;
                min-width: 40px;
            }
        """)

        self.y_pos_slider = QSlider(Qt.Horizontal)
        self.y_pos_slider.setMinimum(-100)
        self.y_pos_slider.setMaximum(100)
        self.y_pos_slider.setValue(0)
        self.y_pos_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid rgba(80, 80, 100, 120);
                height: 6px;
                background: rgba(45, 45, 55, 200);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: rgba(180, 120, 70, 180);
                border: 1px solid rgba(200, 150, 100, 180);
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: rgba(200, 140, 90, 200);
            }
        """)

        self.y_pos_value_label = QLabel("0")
        self.y_pos_value_label.setStyleSheet("""
            QLabel {
                color: rgba(200, 200, 210, 255);
                font-size: 12px;
                min-width: 35px;
            }
        """)

        y_pos_layout.addWidget(y_pos_label)
        y_pos_layout.addWidget(self.y_pos_slider)
        y_pos_layout.addWidget(self.y_pos_value_label)
        control_layout.addLayout(y_pos_layout)

        # 连接滑块信号
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        self.x_pos_slider.valueChanged.connect(self.on_x_pos_changed)
        self.y_pos_slider.valueChanged.connect(self.on_y_pos_changed)

        return control_frame

    def create_status_bar(self):
        """创建状态栏"""
        status_frame = QFrame()
        status_frame.setObjectName("statusFrame")
        status_frame.setStyleSheet("""
            QFrame#statusFrame {
                background-color: rgba(255, 255, 255, 0.03);
                border-radius: 6px;
                border: 1px solid rgba(90, 100, 130, 55);
            }
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 6, 8, 6)
        status_layout.setSpacing(8)

        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(176, 182, 198, 220);
                font-size: 12px;
                padding: 2px 4px;
                background: transparent;
                border: none;
            }
        """)

        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setFixedSize(54, 28)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(82, 88, 108, 150);
                border-radius: 14px;
                color: rgba(235, 237, 244, 255);
                font-size: 12px;
                font-weight: 600;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(101, 108, 132, 180);
            }
            QPushButton:pressed {
                background-color: rgba(70, 76, 94, 180);
            }
        """)
        clear_btn.clicked.connect(self.clear_chat)

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(clear_btn)

        return status_frame

    # ========== 语音相关方法 ==========
    def start_voice_input(self):
        """开始语音输入"""
        self.voice_record_requested.emit()

    @Slot()
    def on_recording_started(self):
        """录音开始时的UI更新"""
        self.voice_btn.setText("🔴 录音中...")
        self.voice_btn.setEnabled(False)
        self.status_label.setText("正在录音...")

    @Slot()
    def on_recording_finished(self):
        """录音结束时的UI更新"""
        self.voice_btn.setText("🎤 语音输入")
        self.voice_btn.setEnabled(True)
        self.status_label.setText("录音完成")

    @Slot()
    def on_transcription_started(self):
        """转录开始时的UI更新"""
        self.status_label.setText("正在识别语音...")

    @Slot(str)
    def on_transcription_finished(self, text):
        """转录完成时的UI更新"""
        self.status_label.setText(f"识别结果: {text[:20]}...")

    @Slot(str)
    def add_voice_message(self, text):
        """添加语音识别的消息"""
        self.add_message("human", text, "用户(语音)")

    @Slot(str)
    def add_ai_response(self, text):
        """添加AI回复"""
        self.add_message("ai", text, "AI助手")

    @Slot(str, int)
    def on_subtitle_display_requested(self, text, seq_id):
        """在TTS片段播放完成后显示对应字幕文本为聊天消息"""
        if text:
            self.add_message("ai", text, "AI助手")

    @Slot(str)
    def update_status(self, status):
        """更新状态"""
        self.status_label.setText(status)

    @Slot(str)
    def show_error(self, error_msg):
        """显示错误信息"""
        self.status_label.setText(f"错误: {error_msg}")

    def toggle_auto_voice_recognition(self):
        """切换自动语音识别状态"""
        self.logger.info(f"用户点击自动识别按钮，当前状态: {'激活' if self.vad_active else '未激活'}")

        if not self.vad_active:
            self.logger.info("准备启动自动语音识别")
            self.start_auto_voice_recognition()
        else:
            self.logger.info("准备停止自动语音识别")
            self.stop_auto_voice_recognition()

    def start_auto_voice_recognition(self):
        """启动自动语音识别"""
        try:
            self.vad_start_time = time.time()
            self.vad_active = True
            self.vad_recording = False
            self.vad_audio_buffer = []
            self.last_speech_time = 0
            self.vad_paused_by_ai = False

            self.logger.info(f"开始启动自动语音识别系统，启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

            self.auto_voice_btn.setText("🔴 监听中...")
            self.auto_voice_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(196, 90, 90, 210);
                    border: none;
                    border-radius: 6px;
                    color: white;
                    font-size: 12px;
                    font-weight: 700;
                    padding: 0 14px;
                }
                QPushButton:hover {
                    background-color: rgba(216, 110, 110, 230);
                }
                QPushButton:pressed {
                    background-color: rgba(176, 74, 74, 220);
                }
            """)
            self.status_label.setText("自动语音识别已启动")

            self.vad_thread = threading.Thread(target=self.vad_listen_thread, daemon=True)
            self.vad_thread.start()

            self.logger.info("VAD监听线程已启动")

        except Exception as e:
            self.logger.error(f"启动自动语音识别失败: {str(e)}")
            self.show_error(f"启动自动语音识别失败: {str(e)}")
            self.vad_active = False

    def stop_auto_voice_recognition(self):
        """停止自动语音识别"""
        stop_time = time.time()
        runtime = stop_time - self.vad_start_time if self.vad_start_time > 0 else 0

        self.logger.info(f"开始停止自动语音识别系统，运行时长: {runtime:.2f}秒")

        self.vad_active = False

        # 更新UI
        self.auto_voice_btn.setText("🎯 自动识别")
        self.auto_voice_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(86, 156, 92, 210);
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: rgba(100, 175, 106, 230);
            }
            QPushButton:pressed {
                background-color: rgba(72, 140, 79, 220);
            }
            QPushButton:disabled {
                background-color: rgba(80, 86, 104, 130);
                color: rgba(160, 165, 180, 180);
            }
        """)
        self.status_label.setText("自动语音识别已停止")

        # 如果有录音缓冲区，处理最后的音频
        if self.vad_audio_buffer and self.vad_recording:
            self.logger.info("处理停止前的最后音频数据")
            self.process_vad_audio()

        # 取消静音计时器
        if self.vad_silence_timer:
            self.logger.info("取消静音计时器")
            self.vad_silence_timer.cancel()
            self.vad_silence_timer = None

        # 等待线程结束
        if self.vad_thread and self.vad_thread.is_alive():
            self.logger.info("等待VAD线程结束")
            try:
                self.vad_thread.join(timeout=2.0)
                if self.vad_thread.is_alive():
                    self.logger.warning("VAD线程未能在2秒内结束，尝试停止音频流以解除阻塞")
                    try:
                        if self.vad_audio_stream:
                            if hasattr(self.vad_audio_stream, 'is_active'):
                                active = False
                                try:
                                    active = self.vad_audio_stream.is_active()
                                except Exception:
                                    pass
                                if active:
                                    self.vad_audio_stream.stop_stream()
                                    self.logger.info("已请求停止音频流")
                            else:
                                self.vad_audio_stream.stop_stream()
                                self.logger.info("已请求停止音频流")
                    except Exception as e:
                        self.logger.error(f"停止音频流以解除阻塞时出错: {str(e)}")

                    try:
                        self.vad_thread.join(timeout=1.0)
                    except Exception:
                        pass

                    if self.vad_thread.is_alive():
                        self.logger.warning("VAD线程仍未结束，将交由守护线程自行退出")
                    else:
                        self.logger.info("VAD线程已成功结束")
                else:
                    self.logger.info("VAD线程已成功结束")
            except Exception as e:
                self.logger.error(f"等待线程结束时出错: {str(e)}")

        # 清理状态
        self.vad_recording = False
        self.vad_audio_buffer = []
        self.last_speech_time = 0
        self.vad_thread = None

        self.logger.info("自动语音识别系统已完全停止，所有资源已释放")

    def vad_listen_thread(self):
        """VAD监听线程"""
        p = None
        try:
            self.logger.info("VAD监听线程开始初始化")

            # VAD设置 - 使用 Silero VAD (CPU)
            torch.set_num_threads(1)
            model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)
            model.eval()
            (get_speech_timestamps, _, read_audio, _, _) = utils
            self.logger.info("Silero VAD引擎初始化完成 (CPU模式)")

            # 音频参数
            RATE = 16000
            CHANNELS = 1
            FORMAT = pyaudio.paInt16
            FRAME_DURATION = 32
            FRAME_SIZE = int(RATE * FRAME_DURATION / 1000)
            FRAME_BYTES = FRAME_SIZE * 2

            self.logger.info(f"音频参数: 采样率={RATE}Hz, 通道数={CHANNELS}, 帧大小={FRAME_SIZE}")

            # 初始化PyAudio
            p = pyaudio.PyAudio()

            self.vad_audio_stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=FRAME_SIZE
            )

            self.logger.info("音频流已成功打开，开始监听语音")

            frame_count = 0
            speech_frames = 0

            while self.vad_active:
                try:
                    # 若AI正在说话，轻量读取并丢弃数据
                    if self.vad_paused_by_ai:
                        try:
                            _ = self.vad_audio_stream.read(FRAME_SIZE, exception_on_overflow=False)
                        except Exception:
                            pass
                        time.sleep(0.01)
                        continue

                    audio_data = self.vad_audio_stream.read(FRAME_SIZE, exception_on_overflow=False)
                    frame_count += 1

                    if len(audio_data) == FRAME_BYTES:
                        audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
                        audio_float32 = audio_int16.astype(np.float32) / 32768.0
                        audio_tensor = torch.from_numpy(audio_float32)

                        speech_prob = model(audio_tensor, RATE).item()
                        is_speech = speech_prob > 0.5

                        if is_speech:
                            speech_frames += 1
                            current_time = time.time()
                            self.last_speech_time = current_time

                            if not self.vad_recording:
                                self.vad_recording = True
                                self.vad_audio_buffer = []
                                self.logger.info(f"检测到语音，开始录音 (帧#{frame_count})")
                                QTimer.singleShot(0, lambda: self.status_label.setText("检测到语音，开始录音..."))

                            self.vad_audio_buffer.append(audio_data)

                            if self.vad_silence_timer:
                                try:
                                    self.vad_silence_timer.cancel()
                                except Exception:
                                    pass
                                self.vad_silence_timer = None

                        else:
                            if self.vad_recording:
                                self.vad_audio_buffer.append(audio_data)

                                if not self.vad_silence_timer:
                                    self.vad_silence_timer = threading.Timer(2.0, self.on_silence_timeout)
                                    self.vad_silence_timer.start()
                                    self.logger.info("启动2秒静音计时器")
                                    QTimer.singleShot(0, lambda: self.status_label.setText("检测到静音，2秒后自动提交..."))

                    if frame_count % 1000 == 0:
                        speech_ratio = speech_frames / frame_count * 100 if frame_count > 0 else 0
                        self.logger.debug(f"处理了{frame_count}帧，语音帧占比: {speech_ratio:.1f}%")

                except Exception as e:
                    if self.vad_active:
                        self.logger.error(f"VAD监听错误: {e}")
                    break

        except Exception as e:
            self.logger.error(f"VAD初始化失败: {str(e)}")
            QTimer.singleShot(0, lambda: self.show_error(f"VAD初始化失败: {str(e)}"))
        finally:
            self.logger.info("VAD监听线程开始清理资源")
            if self.vad_audio_stream:
                try:
                    self.vad_audio_stream.stop_stream()
                    self.vad_audio_stream.close()
                    self.logger.info("音频流已关闭")
                except Exception as e:
                    self.logger.error(f"关闭音频流时出错: {str(e)}")
                finally:
                    self.vad_audio_stream = None
            if p:
                try:
                    p.terminate()
                    self.logger.info("PyAudio已终止")
                except Exception as e:
                    self.logger.error(f"终止PyAudio时出错: {str(e)}")
            self.logger.info("VAD监听线程已结束")

    def on_silence_timeout(self):
        """静音超时处理"""
        if self.vad_recording and self.vad_active:
            silence_duration = time.time() - self.last_speech_time if self.last_speech_time > 0 else 0
            buffer_size = len(self.vad_audio_buffer) if self.vad_audio_buffer else 0
            self.logger.info(f"静音超时触发，静音时长: {silence_duration:.1f}秒，缓冲区大小: {buffer_size}帧")
            QTimer.singleShot(0, self.process_vad_audio)
        else:
            self.logger.warning(f"静音超时触发但条件不满足: recording={self.vad_recording}, active={self.vad_active}")

    def process_vad_audio(self):
        """处理VAD录制的音频"""
        if not self.vad_audio_buffer:
            self.logger.warning("process_vad_audio被调用但音频缓冲区为空")
            return

        try:
            process_start_time = time.time()
            buffer_size = len(self.vad_audio_buffer)

            self.logger.info(f"开始处理音频数据，缓冲区包含{buffer_size}帧")

            self.vad_recording = False
            self.vad_silence_timer = None

            # 将音频数据合并
            audio_data = b''.join(self.vad_audio_buffer)
            self.vad_audio_buffer = []

            audio_duration = len(audio_data) / (16000 * 2)
            self.logger.info(f"音频数据合并完成，总时长: {audio_duration:.2f}秒，数据大小: {len(audio_data)}字节")

            self.status_label.setText("正在识别语音...")

            # 将字节数据转换为numpy数组
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            self.logger.debug(f"音频数据转换为numpy数组，形状: {audio_np.shape}")

            # 通过 WSController 提交音频
            if self.controller and hasattr(self.controller, 'send_audio_bytes'):
                try:
                    self.logger.info("提交音频到WS后端进行自动识别")
                    submit_start = time.time()

                    int16_data = (np.clip(audio_np, -1.0, 1.0) * 32767.0).astype(np.int16)
                    buf = io.BytesIO()
                    sf.write(file=buf, data=int16_data, samplerate=16000, format='WAV')
                    wav_bytes = buf.getvalue()
                    self.controller.send_audio_bytes(wav_bytes)

                    submit_duration = time.time() - submit_start
                    self.logger.info(f"音频提交完成，耗时: {submit_duration:.2f}秒，等待后端转写与回复")
                    self.status_label.setText("已提交音频，等待识别结果")

                except Exception as err:
                    self.logger.error(f"音频提交失败: {str(err)}")
                    self.show_error(f"音频提交失败: {str(err)}")
                    self.mock_asr_result()
            else:
                self.logger.warning("控制器不支持音频提交接口，使用模拟结果")
                self.mock_asr_result()

        except Exception as e:
            self.logger.error(f"处理音频失败: {str(e)}")
            self.show_error(f"处理音频失败: {str(e)}")

    def mock_asr_result(self):
        """模拟ASR识别结果（当真实ASR不可用时的备选方案）"""
        try:
            self.logger.info("使用模拟ASR结果")

            mock_text = "[模拟识别] 检测到语音但无法识别具体内容"

            self.logger.info(f"模拟识别结果: '{mock_text}'")

            # 添加识别结果到聊天
            self.add_message("human", mock_text, "用户(自动识别)")

            # 发送给控制器处理
            self.message_sent.emit(mock_text)

            self.status_label.setText("语音识别完成(模拟)")

            self.logger.info("模拟ASR处理完成，结果已提交")

        except Exception as e:
            self.logger.error(f"模拟ASR处理失败: {str(e)}")
            self.show_error(f"模拟ASR处理失败: {str(e)}")

    # ========== 聊天窗口方法 ==========
    def load_chat_rooms(self):
        """加载聊天室列表"""
        try:
            # 通过后端 WS 请求历史列表
            if hasattr(self.controller, 'request_history_list'):
                self.controller.request_history_list()
                if hasattr(self, 'status_label'):
                    self.status_label.setText("正在加载对话列表...")
                return
        except Exception:
            pass

        # 回退到本地实现
        try:
            histories = get_history_list(self.conf_uid)
            self.room_selector.clear()
            if not histories:
                self.history_uid = create_new_history(self.conf_uid)
                self.room_selector.addItem("默认聊天室", self.history_uid)
                self.current_chat_room = "默认聊天室"
            else:
                for i, history in enumerate(histories):
                    room_name = f"聊天室 {i+1}"
                    if history.get('latest_message'):
                        content = history['latest_message'].get('content', '')
                        room_name = content[:20] + "..." if len(content) > 20 else (content or room_name)
                    self.room_selector.addItem(room_name, history['uid'])
                if self.room_selector.count() > 0:
                    self.history_uid = self.room_selector.itemData(0)
                    self.current_chat_room = self.room_selector.itemText(0)
            self.status_label.setText(f"已加载 {self.room_selector.count()} 个聊天室")
        except Exception as e:
            print(f"加载聊天室列表时出错: {e}")
            self.status_label.setText("加载聊天室失败")

    def switch_chat_room(self, room_name):
        """切换聊天室"""
        if not room_name:
            return

        try:
            current_index = self.room_selector.currentIndex()
            if current_index >= 0:
                self.history_uid = self.room_selector.itemData(current_index)
                self.current_chat_room = room_name
                self.clear_chat_display()
                self.load_chat_history()
                self.status_label.setText(f"已切换到: {room_name}")

        except Exception as e:
            print(f"切换聊天室时出错: {e}")
            self.status_label.setText("切换聊天室失败")

    def create_new_chat_room(self):
        """创建新聊天室"""
        try:
            dialog = QInputDialog(self)
            dialog.setWindowTitle("创建新聊天室")
            dialog.setLabelText("请输入聊天室名称:")
            dialog.setTextValue("新聊天室")

            dialog.setStyleSheet("""
                QInputDialog {
                    background-color: #1d2130;
                    color: #eef0f8;
                }
                QLabel {
                    color: #eef0f8;
                    background-color: transparent;
                }
                QLineEdit {
                    background-color: #2b3042;
                    color: #eef0f8;
                    border: 1px solid #57627f;
                    border-radius: 8px;
                    padding: 6px 8px;
                }
                QPushButton {
                    background-color: #4d90d7;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 14px;
                    min-width: 60px;
                }
                QPushButton:hover {
                    background-color: #5fa1e6;
                }
            """)

            if dialog.exec_() == QInputDialog.Accepted:
                room_name = dialog.textValue().strip()
                if room_name:
                    if hasattr(self.controller, 'request_create_new_history'):
                        self.controller.request_create_new_history()
                        if hasattr(self, 'status_label'):
                            self.status_label.setText(f"正在创建聊天室: {room_name}")
                    else:
                        new_history_uid = create_new_history(self.conf_uid)
                        if new_history_uid:
                            self.room_selector.addItem(room_name, new_history_uid)
                            self.room_selector.setCurrentIndex(self.room_selector.count() - 1)
                            self.status_label.setText(f"已创建聊天室: {room_name}")

        except Exception as e:
            print(f"创建新聊天室时出错: {e}")

    def get_current_time(self):
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    def add_message(self, role: str, content: str, name: str = None):
        """添加消息到聊天界面"""
        try:
            # 创建消息容器
            message_frame = QFrame()
            message_layout = QVBoxLayout(message_frame)
            message_layout.setContentsMargins(8, 6, 8, 6)
            message_layout.setSpacing(3)

            # 根据角色设置统一的样式
            if role == "human":
                bg_color = "rgba(78, 126, 205, 0.26)"
                border_color = "rgba(105, 154, 235, 0.28)"
                align = Qt.AlignRight
                name_text = name or "用户"
                margin_style = "margin-left: 56px; margin-right: 4px;"
            else:
                bg_color = "rgba(66, 145, 111, 0.26)"
                border_color = "rgba(93, 181, 139, 0.25)"
                align = Qt.AlignLeft
                name_text = name or "AI助手"
                margin_style = "margin-left: 4px; margin-right: 56px;"

            message_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border-radius: 14px;
                    border: 1px solid {border_color};
                    {margin_style}
                }}
            """)

            # 发送者名称
            name_label = QLabel(name_text)
            name_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 210);
                    font-size: 12px;
                    font-weight: 700;
                    padding: 0 4px;
                    border: none;
                    background: transparent;
                }
            """)
            name_label.setAlignment(align)

            # 消息内容
            content_label = QLabel(content)
            content_label.setWordWrap(True)
            content_label.setStyleSheet("""
                QLabel {
                    color: rgba(247, 248, 251, 255);
                    font-size: 12px;
                    padding: 4px 6px;
                    line-height: 1.55;
                    border: none;
                    background: transparent;
                }
            """)
            content_label.setAlignment(align)

            # 时间戳
            time_label = QLabel(self.get_current_time())
            time_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 130);
                    font-size: 10px;
                    padding: 0 4px;
                    border: none;
                    background: transparent;
                }
            """)
            time_label.setAlignment(align)

            message_layout.addWidget(name_label)
            message_layout.addWidget(content_label)
            message_layout.addWidget(time_label)

            # 添加到聊天布局
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, message_frame)

            # 滚动到底部
            QTimer.singleShot(100, self.scroll_to_bottom)

            # 由后端接管历史存储，不再执行本地写入
            # 原本: store_message(self.conf_uid, self.history_uid, role, content)

        except Exception as e:
            print(f"添加消息时出错: {e}")

    def scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.chat_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_chat_display(self):
        """清空聊天显示"""
        while self.chat_layout.count() > 1:
            child = self.chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def clear_chat(self):
        """清空聊天"""
        self.clear_chat_display()
        self.status_label.setText("聊天记录已清空")

    def load_chat_history(self):
        """加载聊天历史"""
        try:
            if hasattr(self.controller, 'request_fetch_and_set_history') and getattr(self, 'history_uid', None):
                self.controller.request_fetch_and_set_history(self.history_uid)
                if hasattr(self, 'status_label'):
                    self.status_label.setText("正在加载消息...")
                return
        except Exception:
            pass

        # 回退到本地实现
        try:
            history = get_history(self.conf_uid, self.history_uid)
            if history:
                for msg in history:
                    self.add_message(
                        msg['role'],
                        msg['content'],
                        "用户" if msg['role'] == "human" else "AI助手"
                    )
        except Exception as e:
            print(f"加载聊天历史时出错: {e}")

    # --- 历史记录信号回调 ---
    def on_history_list_received(self, histories: list):
        try:
            self.room_selector.clear()
            for h in histories:
                latest = h.get('latest_message')
                if isinstance(latest, dict):
                    display = latest.get('content') or latest.get('text') or h.get('uid') or '新会话'
                else:
                    display = latest or h.get('uid') or '新会话'
                self.room_selector.addItem(str(display), h.get('uid'))
            if histories:
                self.history_uid = histories[0].get('uid')
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"已加载 {self.room_selector.count()} 个聊天室")
        except Exception as e:
            print(f"处理历史列表失败: {e}")

    def on_history_data_received(self, messages: list):
        try:
            self.clear_chat_display()
            for m in messages:
                role = m.get('role') or 'assistant'
                text = m.get('text') or m.get('content') or ''
                self.add_message(role, text, "用户" if role == "human" else "AI助手")
            if hasattr(self, 'status_label'):
                self.status_label.setText('已加载消息')
        except Exception as e:
            print(f"处理历史数据失败: {e}")

    def on_new_history_created(self, uid: str):
        try:
            self.history_uid = uid
            self.controller.request_fetch_and_set_history(uid)
            if hasattr(self, 'status_label'):
                self.status_label.setText('新会话已创建')
        except Exception as e:
            print(f"处理新会话失败: {e}")

    def on_history_deleted(self, success: bool):
        try:
            if hasattr(self, 'status_label'):
                self.status_label.setText('会话已删除' if success else '会话删除失败')
            self.controller.request_history_list()
        except Exception as e:
            print(f"处理会话删除失败: {e}")

    def refresh_chat_content(self):
        """刷新聊天内容"""
        pass

    def send_message(self):
        """发送消息"""
        text = self.input_text.toPlainText().strip()
        if text:
            self.add_message("human", text, "用户")
            self.input_text.clear()
            self.message_sent.emit(text)

    def eventFilter(self, obj, event):
        """事件过滤器 - 处理回车发送"""
        if obj == self.input_text and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    def close_window(self):
        """关闭窗口"""
        self.logger.info("开始关闭聊天窗口")

        if self.vad_active:
            self.logger.info("检测到VAD正在运行，先停止自动语音识别")
            self.stop_auto_voice_recognition()
        else:
            self.logger.info("VAD未运行，直接关闭窗口")

        self.window_closed.emit()
        self.close()

        self.logger.info("聊天窗口已关闭")

    def mousePressEvent(self, event):
        """鼠标按下事件 - 开始拖动"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 执行拖动"""
        if event.buttons() == Qt.LeftButton and self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件 - 结束拖动"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()

    @Slot()
    def on_ai_audio_started(self):
        """AI开始输出语音时，暂停VAD监听"""
        if self.vad_active and not self.vad_paused_by_ai:
            if self.vad_silence_timer:
                try:
                    self.vad_silence_timer.cancel()
                except Exception:
                    pass
                self.vad_silence_timer = None
            self.vad_paused_by_ai = True
            self.logger.info("AI开始说话，暂停VAD监听")
            self.status_label.setText("AI正在说话，已暂停监听")

    @Slot()
    def on_ai_audio_finished(self):
        """AI语音结束后，恢复VAD监听"""
        if self.vad_active and self.vad_paused_by_ai:
            self.vad_paused_by_ai = False
            self.logger.info("AI语音结束，恢复VAD监听")
            self.status_label.setText("自动语音识别已恢复")

    # # 若你项目里已有这几个方法，可保留你自己的实现
    # def on_scale_changed(self, value):
    #     if hasattr(self, 'scale_value_label'):
    #         self.scale_value_label.setText(f"{value}%")
    #
    # def on_x_pos_changed(self, value):
    #     if hasattr(self, 'x_pos_value_label'):
    #         self.x_pos_value_label.setText(str(value))
    #
    # def on_y_pos_changed(self, value):
    #     if hasattr(self, 'y_pos_value_label'):
    #         self.y_pos_value_label.setText(str(value))