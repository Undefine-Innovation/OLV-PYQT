from PyQt5.QtCore import Qt, QEvent, QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QPushButton, QApplication,
    QHBoxLayout, QScrollArea, QTextEdit, QFrame, QComboBox, QInputDialog, QSlider
)
import pyaudio
import webrtcvad
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
    window_closed = pyqtSignal()
    message_sent = pyqtSignal(str)
    voice_record_requested = pyqtSignal()  # 新增：语音录音请求信号
    
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
        # 新增：AI说话期间暂停VAD的标志
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
        # 连接发送信号到控制器
        self.message_sent.connect(self.controller.on_text_sent)
        self.voice_record_requested.connect(self.controller.on_voice_record_request)
        
        # 连接控制器回复信号
        self.controller.ai_response.connect(self.add_ai_response)
        self.controller.asr_result.connect(self.add_voice_message)
        self.controller.status_updated.connect(self.update_status)
        self.controller.error_occurred.connect(self.show_error)

        # 新增：连接字幕显示信号以显示AI说话文本（WSController使用该信号）
        if hasattr(self.controller, 'subtitle_display_requested'):
            try:
                self.controller.subtitle_display_requested.connect(self.on_subtitle_display_requested)
            except Exception:
                pass

        # 新增：接入AI语音开始/结束以控制VAD暂停与恢复
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

        # 新增：接入历史记录相关信号
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
        self.resize(450, 750)  # 增加宽度以容纳语音按钮
        
        # 设置初始位置（屏幕右侧）
        screen = QApplication.desktop().screenGeometry()
        self.move(screen.width() - 470, 50)
        
    def setup_ui(self):
        """设置UI界面"""
        # 主容器
        main_container = QFrame(self)
        main_container.setStyleSheet("""
            QFrame {
                background-color: rgba(25, 25, 35, 240);
                border-radius: 15px;
                border: 1px solid rgba(80, 80, 100, 120);
            }
        """)
        
        # 主布局
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # 标题栏
        title_bar = self.create_title_bar()
        main_layout.addWidget(title_bar)
        
        # 聊天室选择区域
        chat_room_area = self.create_chat_room_selector()
        main_layout.addWidget(chat_room_area)
        
        # 聊天内容区域
        self.chat_area = self.create_chat_area()
        main_layout.addWidget(self.chat_area)
        
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
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title_label = QLabel("🎤 AI语音聊天")
        title_label.setStyleSheet("""
            QLabel {
                color: rgba(220, 220, 230, 255);
                font-size: 16px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        
        # 最小化按钮
        minimize_btn = QPushButton("−")
        minimize_btn.setFixedSize(30, 30)
        minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(80, 80, 100, 120);
                border-radius: 15px;
                color: rgba(220, 220, 230, 255);
                font-size: 18px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(100, 100, 120, 160);
            }
            QPushButton:pressed {
                background-color: rgba(60, 60, 80, 120);
            }
        """)
        minimize_btn.clicked.connect(self.showMinimized)
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(180, 60, 60, 150);
                border-radius: 15px;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(200, 80, 80, 180);
            }
            QPushButton:pressed {
                background-color: rgba(160, 40, 40, 150);
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
        selector_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(35, 35, 45, 180);
                border-radius: 10px;
                border: 1px solid rgba(80, 80, 100, 100);
            }
        """)
        
        selector_layout = QHBoxLayout(selector_frame)
        selector_layout.setContentsMargins(10, 8, 10, 8)
        selector_layout.setSpacing(8)
        
        # 聊天室标签
        room_label = QLabel("聊天室:")
        room_label.setStyleSheet("""
            QLabel {
                color: rgba(220, 220, 230, 255);
                font-size: 14px;
                font-weight: bold;
            }
        """)
        
        # 聊天室下拉选择框
        self.room_selector = QComboBox()
        self.room_selector.setMinimumWidth(150)
        self.room_selector.setStyleSheet("""
            QComboBox {
                background-color: rgba(45, 45, 55, 200);
                border: 1px solid rgba(80, 80, 100, 120);
                border-radius: 8px;
                color: rgba(220, 220, 230, 255);
                font-size: 14px;
                padding: 5px 10px;
                min-height: 25px;
            }
            QComboBox:hover {
                border: 2px solid rgba(100, 150, 200, 180);
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid rgba(220, 220, 230, 255);
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(45, 45, 55, 240);
                border: 1px solid rgba(80, 80, 100, 120);
                border-radius: 8px;
                color: rgba(220, 220, 230, 255);
                selection-background-color: rgba(70, 130, 180, 180);
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                border: none;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: rgba(70, 130, 180, 120);
            }
        """)
        self.room_selector.currentTextChanged.connect(self.switch_chat_room)
        
        # 新建聊天室按钮
        new_room_btn = QPushButton("+")
        new_room_btn.setFixedSize(35, 35)
        new_room_btn.setToolTip("创建新聊天室")
        new_room_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(70, 130, 180, 180);
                border: none;
                border-radius: 17px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(90, 150, 200, 200);
            }
            QPushButton:pressed {
                background-color: rgba(50, 110, 160, 180);
            }
        """)
        new_room_btn.clicked.connect(self.create_new_chat_room)
        
        selector_layout.addWidget(room_label)
        selector_layout.addWidget(self.room_selector)
        selector_layout.addWidget(new_room_btn)
        
        return selector_frame
        
    def create_chat_area(self):
        """创建聊天内容区域"""
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: rgba(60, 60, 80, 80);
                width: 8px;
                border-radius: 4px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(120, 120, 140, 150);
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(140, 140, 160, 180);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        # 聊天内容容器
        self.chat_content = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setContentsMargins(5, 5, 5, 5)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()
        
        scroll_area.setWidget(self.chat_content)
        
        return scroll_area
        
    def create_input_area(self):
        """创建输入区域（包含语音按钮）"""
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(35, 35, 45, 180);
                border-radius: 10px;
                border: 1px solid rgba(80, 80, 100, 100);
            }
        """)
        
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 8, 10, 8)
        input_layout.setSpacing(8)
        
        # 文本输入行
        text_input_layout = QHBoxLayout()
        
        # 输入框
        self.input_text = QTextEdit()
        self.input_text.setMaximumHeight(80)
        self.input_text.setMinimumHeight(35)
        self.input_text.setPlaceholderText("输入消息...")
        self.input_text.setStyleSheet("""
            QTextEdit {
                background-color: rgba(45, 45, 55, 200);
                border: 1px solid rgba(80, 80, 100, 120);
                border-radius: 8px;
                color: rgba(220, 220, 230, 255);
                font-size: 14px;
                padding: 8px;
            }
            QTextEdit:focus {
                border: 2px solid rgba(100, 150, 200, 180);
            }
        """)
        
        # 绑定回车键发送
        self.input_text.installEventFilter(self)
        
        # 发送按钮
        send_btn = QPushButton("发送")
        send_btn.setFixedSize(60, 35)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(70, 130, 180, 180);
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(90, 150, 200, 200);
            }
            QPushButton:pressed {
                background-color: rgba(50, 110, 160, 180);
            }
            QPushButton:disabled {
                background-color: rgba(80, 80, 100, 120);
                color: rgba(150, 150, 150, 150);
            }
        """)
        send_btn.clicked.connect(self.send_message)
        
        text_input_layout.addWidget(self.input_text)
        text_input_layout.addWidget(send_btn)
        
        # 语音按钮行
        voice_layout = QHBoxLayout()
        
        # 自动语音识别按钮
        self.auto_voice_btn = QPushButton("🎯 自动识别")
        self.auto_voice_btn.setFixedHeight(40)
        self.auto_voice_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 180, 100, 180);
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(120, 200, 120, 200);
            }
            QPushButton:pressed {
                background-color: rgba(80, 160, 80, 180);
            }
            QPushButton:disabled {
                background-color: rgba(80, 80, 100, 120);
                color: rgba(150, 150, 150, 150);
            }
        """)
        self.auto_voice_btn.clicked.connect(self.toggle_auto_voice_recognition)
        
        # 语音录制按钮
        self.voice_btn = QPushButton("🎤 语音输入")
        self.voice_btn.setFixedHeight(40)
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(220, 100, 100, 180);
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(240, 120, 120, 200);
            }
            QPushButton:pressed {
                background-color: rgba(200, 80, 80, 180);
            }
            QPushButton:disabled {
                background-color: rgba(80, 80, 100, 120);
                color: rgba(150, 150, 150, 150);
            }
        """)
        self.voice_btn.clicked.connect(self.start_voice_input)
        
        voice_layout.addWidget(self.auto_voice_btn)
        voice_layout.addWidget(self.voice_btn)
        
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
                font-size: 14px;
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
        self.x_pos_slider.setMinimum(-100)  # 左移100像素
        self.x_pos_slider.setMaximum(100)   # 右移100像素
        self.x_pos_slider.setValue(0)       # 默认居中
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
        self.y_pos_slider.setMinimum(-100)  # 上移100像素
        self.y_pos_slider.setMaximum(100)   # 下移100像素
        self.y_pos_slider.setValue(0)       # 默认居中
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
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(160, 160, 180, 200);
                font-size: 12px;
                padding: 3px;
            }
        """)
        
        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setFixedSize(50, 25)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(80, 80, 100, 120);
                border-radius: 12px;
                color: rgba(220, 220, 230, 255);
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(100, 100, 120, 160);
            }
            QPushButton:pressed {
                background-color: rgba(60, 60, 80, 120);
            }
        """)
        clear_btn.clicked.connect(self.clear_chat)
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(clear_btn)
        
        return status_frame
        
    # 语音相关方法
    def start_voice_input(self):
        """开始语音输入"""
        self.voice_record_requested.emit()
        
    @pyqtSlot()
    def on_recording_started(self):
        """录音开始时的UI更新"""
        self.voice_btn.setText("🔴 录音中...")
        self.voice_btn.setEnabled(False)
        self.status_label.setText("正在录音...")
        
    @pyqtSlot()
    def on_recording_finished(self):
        """录音结束时的UI更新"""
        self.voice_btn.setText("🎤 语音输入")
        self.voice_btn.setEnabled(True)
        self.status_label.setText("录音完成")
        
    @pyqtSlot()
    def on_transcription_started(self):
        """转录开始时的UI更新"""
        self.status_label.setText("正在识别语音...")
        
    @pyqtSlot(str)
    def on_transcription_finished(self, text):
        """转录完成时的UI更新"""
        self.status_label.setText(f"识别结果: {text[:20]}...")
        
    @pyqtSlot(str)
    def add_voice_message(self, text):
        """添加语音识别的消息"""
        self.add_message("human", text, "用户(语音)")
        
    @pyqtSlot(str)
    def add_ai_response(self, text):
        """添加AI回复"""
        self.add_message("ai", text, "AI助手")

    @pyqtSlot(str, int)
    def on_subtitle_display_requested(self, text, seq_id):
        """在TTS片段播放完成后显示对应字幕文本为聊天消息"""
        # 与 add_ai_response 一致，直接将字幕文本作为AI消息显示
        if text:
            self.add_message("ai", text, "AI助手")
        
    @pyqtSlot(str)
    def update_status(self, status):
        """更新状态"""
        self.status_label.setText(status)
        
    @pyqtSlot(str)
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
            # 新增：启动时确保未暂停
            self.vad_paused_by_ai = False
            
            self.logger.info(f"开始启动自动语音识别系统，启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            self.auto_voice_btn.setText("🔴 监听中...")
            self.auto_voice_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(220, 100, 100, 180);
                    border: none;
                    border-radius: 8px;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(240, 120, 120, 200);
                }
                QPushButton:pressed {
                    background-color: rgba(200, 80, 80, 180);
                }
            """)
            self.status_label.setText("自动语音识别已启动")
            
            # 启动VAD监听线程
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
                background-color: rgba(100, 180, 100, 180);
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(120, 200, 120, 200);
            }
            QPushButton:pressed {
                background-color: rgba(80, 160, 80, 180);
            }
            QPushButton:disabled {
                background-color: rgba(80, 80, 100, 120);
                color: rgba(150, 150, 150, 150);
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
            
        # 等待线程结束（先不在主线程关闭音频流，避免读操作崩溃）
        if self.vad_thread and self.vad_thread.is_alive():
            self.logger.info("等待VAD线程结束")
            try:
                self.vad_thread.join(timeout=2.0)  # 最多等待2秒
                if self.vad_thread.is_alive():
                    self.logger.warning("VAD线程未能在2秒内结束，尝试停止音频流以解除阻塞")
                    # 尝试仅停止音频流来解除阻塞（不在主线程进行close，避免双重关闭）
                    try:
                        if self.vad_audio_stream:
                            # 若仍在活动，停止它以解除read阻塞
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
                                # 不支持is_active属性时，直接尝试停止
                                self.vad_audio_stream.stop_stream()
                                self.logger.info("已请求停止音频流")
                    except Exception as e:
                        self.logger.error(f"停止音频流以解除阻塞时出错: {str(e)}")
                    # 再次等待短时间
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
            
            # VAD设置
            #TODO：动态设置VAD
            vad = webrtcvad.Vad(1)  # 灵敏度设置为1（0-3，3最敏感）
            self.logger.info("VAD引擎初始化完成，灵敏度设置为1")
            
            # 音频参数
            RATE = 16000
            CHANNELS = 1
            FORMAT = pyaudio.paInt16
            FRAME_DURATION = 30  # ms
            FRAME_SIZE = int(RATE * FRAME_DURATION / 1000)  # 480 samples for 30ms
            FRAME_BYTES = FRAME_SIZE * 2  # 2 bytes per sample (16-bit PCM)
            
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
                    # 若AI正在说话，轻量读取并丢弃数据，避免阻塞与资源浪费
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
                        # 检测是否有语音
                        is_speech = vad.is_speech(audio_data, RATE)
                        
                        if is_speech:
                            speech_frames += 1
                            current_time = time.time()
                            self.last_speech_time = current_time
                            
                            if not self.vad_recording:
                                # 开始录音
                                self.vad_recording = True
                                self.vad_audio_buffer = []
                                self.logger.info(f"检测到语音，开始录音 (帧#{frame_count})")
                                QTimer.singleShot(0, lambda: self.status_label.setText("检测到语音，开始录音..."))
                                
                            # 添加音频数据到缓冲区
                            self.vad_audio_buffer.append(audio_data)
                            
                            # 取消之前的静音计时器并重新设置
                            if self.vad_silence_timer:
                                try:
                                    self.vad_silence_timer.cancel()
                                except Exception:
                                    pass
                                self.vad_silence_timer = None
                                self.logger.debug("检测到新语音，重置2秒计时器")
                                
                        else:
                            # 没有检测到语音
                            if self.vad_recording:
                                # 如果正在录音，添加静音数据
                                self.vad_audio_buffer.append(audio_data)
                                
                                # 如果没有静音计时器，立即开始2秒静音计时
                                if not self.vad_silence_timer:
                                    self.vad_silence_timer = threading.Timer(2.0, self.on_silence_timeout)
                                    self.vad_silence_timer.start()
                                    self.logger.info("启动2秒静音计时器")
                                    QTimer.singleShot(0, lambda: self.status_label.setText("检测到静音，2秒后自动提交..."))
                    
                    # 每1000帧记录一次统计信息
                    if frame_count % 1000 == 0:
                        speech_ratio = speech_frames / frame_count * 100 if frame_count > 0 else 0
                        self.logger.debug(f"处理了{frame_count}帧，语音帧占比: {speech_ratio:.1f}%")
                        
                except Exception as e:
                    if self.vad_active:  # 只在仍然活跃时报告错误
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

            audio_duration = len(audio_data) / (16000 * 2)  # 16kHz, 16-bit
            self.logger.info(f"音频数据合并完成，总时长: {audio_duration:.2f}秒，数据大小: {len(audio_data)}字节")

            self.status_label.setText("正在识别语音...")

            # 将字节数据转换为numpy数组
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            self.logger.debug(f"音频数据转换为numpy数组，形状: {audio_np.shape}")

            # 通过 WSController 提交音频，等待后端转写结果
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
             
             # 模拟一个识别结果
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
        
    # 以下是原有的聊天窗口方法（保持不变）
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
        # 回退到本地实现（仅当WS不可用时）
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
                    background-color: white;
                    color: black;
                }
                QLabel {
                    color: black;
                    background-color: transparent;
                }
                QLineEdit {
                    background-color: white;
                    color: black;
                    border: 1px solid gray;
                    padding: 5px;
                }
                QPushButton {
                    background-color: #f0f0f0;
                    color: black;
                    border: 1px solid gray;
                    padding: 5px 15px;
                    min-width: 60px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            
            if dialog.exec_() == QInputDialog.Accepted:
                room_name = dialog.textValue().strip()
                if room_name:
                    # 由后端创建新历史会话
                    if hasattr(self.controller, 'request_create_new_history'):
                        self.controller.request_create_new_history()
                        if hasattr(self, 'status_label'):
                            self.status_label.setText(f"正在创建聊天室: {room_name}")
                    else:
                        # 回退到本地创建
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
            message_layout.setContentsMargins(10, 8, 10, 8)
            message_layout.setSpacing(4)
            
            # 根据角色设置统一的样式
            if role == "human":
                bg_color = "rgba(70, 130, 180, 100)"  # 用户消息 - 蓝色
                align = Qt.AlignRight
                name_text = name or "用户"
                margin_style = "margin-left: 40px; margin-right: 5px;"
            else:  # ai
                bg_color = "rgba(80, 150, 120, 100)"  # AI消息 - 绿色
                align = Qt.AlignLeft
                name_text = name or "AI助手"
                margin_style = "margin-left: 5px; margin-right: 40px;"
                
            message_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_color};
                    border-radius: 12px;
                    border: 1px solid rgba(255, 255, 255, 30);
                    {margin_style}
                }}
            """)
            
            # 发送者名称
            name_label = QLabel(name_text)
            name_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 220);
                    font-size: 12px;
                    font-weight: bold;
                    padding: 2px 4px;
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
                    color: rgba(255, 255, 255, 255);
                    font-size: 14px;
                    padding: 4px 6px;
                    line-height: 1.4;
                    border: none;
                    background: transparent;
                }
            """)
            content_label.setAlignment(align)
            
            # 时间戳
            time_label = QLabel(self.get_current_time())
            time_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 150);
                    font-size: 10px;
                    padding: 2px 4px;
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
        while self.chat_layout.count() > 1:  # 保留最后的弹性空间
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
        # 回退到本地实现（仅当WS不可用时）
        try:
            history = get_history(self.conf_uid, self.history_uid)
            if history:
                for msg in history:
                    self.add_message(msg['role'], msg['content'],
                                     "用户" if msg['role'] == "human" else "AI助手")
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
            # 创建后自动拉取消息（通常为空）
            self.controller.request_fetch_and_set_history(uid)
            if hasattr(self, 'status_label'):
                self.status_label.setText('新会话已创建')
        except Exception as e:
            print(f"处理新会话失败: {e}")

    def on_history_deleted(self, success: bool):
        try:
            if hasattr(self, 'status_label'):
                self.status_label.setText('会话已删除' if success else '会话删除失败')
            # 重新拉取列表
            self.controller.request_history_list()
        except Exception as e:
            print(f"处理会话删除失败: {e}")
            
    def refresh_chat_content(self):
        """刷新聊天内容"""
        pass  # 可以在这里添加实时更新逻辑
        
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
        
        # 停止VAD如果正在运行
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
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 执行拖动"""
        if event.buttons() == Qt.LeftButton and self.dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件 - 结束拖动"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()

    @pyqtSlot()
    def on_ai_audio_started(self):
        """AI开始输出语音时，暂停VAD监听"""
        if self.vad_active and not self.vad_paused_by_ai:
            # 取消静音计时器，防止在AI说话期间提交
            if self.vad_silence_timer:
                try:
                    self.vad_silence_timer.cancel()
                except Exception:
                    pass
                self.vad_silence_timer = None
            self.vad_paused_by_ai = True
            self.logger.info("AI开始说话，暂停VAD监听")
            self.status_label.setText("AI正在说话，已暂停监听")

    @pyqtSlot()
    def on_ai_audio_finished(self):
        """AI语音结束后，恢复VAD监听"""
        if self.vad_active and self.vad_paused_by_ai:
            self.vad_paused_by_ai = False
            self.logger.info("AI语音结束，恢复VAD监听")
            self.status_label.setText("自动语音识别已恢复")
