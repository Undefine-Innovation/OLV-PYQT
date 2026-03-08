import sys
import logging
from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication

# Configure logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Dummy controller providing required signals and slots
class DummyController(QObject):
    ai_response = pyqtSignal(str)
    asr_result = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    subtitle_display_requested = pyqtSignal(str, int)
    audio_playback_started = pyqtSignal()
    audio_playback_finished = pyqtSignal()

    def on_text_sent(self, text: str):
        pass

    def on_voice_record_request(self):
        pass


def main():
    from OQWindows.chat_floating_window import ChatFloatingWindow

    app = QApplication(sys.argv)
    ctrl = DummyController()
    win = ChatFloatingWindow(controller=ctrl)

    # Start VAD, then stop after 1.5 seconds
    QTimer.singleShot(500, win.start_auto_voice_recognition)
    QTimer.singleShot(2000, win.stop_auto_voice_recognition)
    # Quit app shortly after
    QTimer.singleShot(3500, app.quit)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()