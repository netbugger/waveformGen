import os
import sys
import numpy as np
import csv
import serial.tools.list_ports
import pyqtgraph as pg
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QComboBox, QSlider, QLineEdit, QPushButton, 
                             QLabel, QFileDialog, QMessageBox, QProgressDialog)
import time
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer
import pyvisa
"""
python -m nuitka --standalone --onefile --disable-console ^
--jobs=8 ^
--enable-plugin=pyqt5 ^
--output-dir=build_out ^
waveformGen.py
"""
class TransferWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, inst, dac_data, freq, vpp, offset):
        super().__init__()
        self.inst = inst
        self.dac_data = dac_data
        self.freq = freq
        self.vpp = vpp
        self.offset = offset

    def run(self):
        try:
            self.inst.write("*CLS")
            # 여기서 블로킹 발생 (약 60초간 이 쓰레드는 멈춤)
            self.inst.write_binary_values("DATA:DAC VOLATILE, ", self.dac_data, 
                                          datatype='h', is_big_endian=True)
            
            # 전송 후 설정 마무리
            self.inst.write(f'APPLy:USER {self.freq}, {self.vpp}, {self.offset}')
            time.sleep(0.5)
            self.inst.write("FUNC:USER VOLATILE")
            
            self.finished.emit(True, "Success")
            print('signal emit')
        except Exception as e:
            self.finished.emit(False, str(e))

class SignalGeneratorGUI(QMainWindow):
    # 기본 통신 설정
    BAUD_RATE = 2400

    def __init__(self):
        super().__init__()
        self.inst = None
        self.addr = None
        self.waveform_data = None
        self.rm = pyvisa.ResourceManager()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("HP 33120A - Waveform Visualizer (Custom Points)")
        self.setGeometry(100, 100, 1000, 650)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- 좌측 컨트롤 패널 ---
        control_panel = QVBoxLayout()
        
        # 1. 포트 설정
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        port_layout.addWidget(self.port_combo)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_instrument)
        port_layout.addWidget(self.btn_connect)
        control_panel.addLayout(port_layout)

        # 2. 포인트 수 설정 (슬라이더 + 에디트 박스)
        control_panel.addWidget(QLabel("Output Points (8 - 8000):"))
        points_layout = QHBoxLayout()
        self.points_edit = QLineEdit("1000")
        self.points_slider = QSlider(Qt.Horizontal)
        self.points_slider.setRange(8, 8000)
        self.points_slider.setValue(1000)
        points_layout.addWidget(self.points_edit)
        points_layout.addWidget(self.points_slider)
        control_panel.addLayout(points_layout)

        # 3. 전압/오프셋/주파수 설정
        control_panel.addWidget(QLabel("Peak Voltage (V):"))
        self.volt_combo = QComboBox()
        volts = [str(round(x * 0.5, 1)) for x in range(-10, 11) if x != 0]
        self.volt_combo.addItems(volts)
        self.volt_combo.setCurrentText("3.0") 
        control_panel.addWidget(self.volt_combo)

        control_panel.addWidget(QLabel("Offset (VDC):"))
        self.offset_edit = QLineEdit("0.0")
        control_panel.addWidget(self.offset_edit)

        control_panel.addWidget(QLabel("Frequency (Hz):"))
        self.freq_edit = QLineEdit("1000")
        control_panel.addWidget(self.freq_edit)

        # 4. 조작 버튼
        self.btn_load_csv = QPushButton("1. Load CSV")
        self.btn_load_csv.setMinimumHeight(40)
        self.btn_load_csv.clicked.connect(self.load_csv)
        control_panel.addWidget(self.btn_load_csv)

        self.btn_apply = QPushButton("2. Apply & Output")
        self.btn_apply.setMinimumHeight(60)
        self.btn_apply.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold;")
        self.btn_apply.clicked.connect(self.apply_settings)
        control_panel.addWidget(self.btn_apply)
        
        control_panel.addStretch()
        main_layout.addLayout(control_panel, 1)

        # --- 우측 그래프 패널 ---
        self.graph_widget = pg.PlotWidget()
        self.graph_widget.setBackground('k')
        self.graph_widget.showGrid(x=True, y=True)
        self.graph_widget.setLabel('left', 'Value', units='-1 to 1')
        self.graph_widget.setLabel('bottom', 'Points')
        self.graph_widget.addLegend()
        main_layout.addWidget(self.graph_widget, 3)

        # --- 이벤트 연결 (슬라이더/에디트 동기화) ---
        self.points_slider.valueChanged.connect(self.sync_points_from_slider)
        self.points_edit.editingFinished.connect(self.sync_points_from_edit)

    def sync_points_from_slider(self, val):
        self.points_edit.setText(str(val))
        self.update_plot()

    def sync_points_from_edit(self):
        try:
            val = int(self.points_edit.text())
            val = max(8, min(8000, val))
            self.points_slider.setValue(val)
            self.points_edit.setText(str(val))
            self.update_plot()
        except: pass

    def refresh_ports(self):
        self.port_combo.clear()
        for port in serial.tools.list_ports.comports():
            self.port_combo.addItem(port.device)

    def connect_instrument(self):
        port_num = self.port_combo.currentText().replace("COM", "")
        if not port_num: return
        self.addr = f"ASRL{port_num}::INSTR"
        try:
            if self.inst: self.inst.close()
            self.inst = self.rm.open_resource(self.addr)
            self.inst.baud_rate = self.BAUD_RATE
            self.inst.data_bits = 8
            self.inst.stop_bits = pyvisa.constants.StopBits.two
            self.inst.timeout = 120000 # 2400bps 고려 120초
            
            idn = self.inst.query("*IDN?")
            if '33120A' in idn:
                self.btn_connect.setText("Connected")
                self.btn_connect.setStyleSheet("background-color: #27ae60; color: white;")
                QMessageBox.information(self, "Success", f"Connected to {idn.strip()}")
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def load_csv(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Open CSV', '', 'CSV Files (*.csv)')
        if fname:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.waveform_data = np.array([float(row['Data']) for row in reader])
                    
                # CSV 데이터 개수에 맞춰 슬라이더 초기값 설정 (최대 8000)
                data_count = len(self.waveform_data)
                target_points = min(8000, data_count)
                self.points_slider.setValue(target_points)
                self.points_edit.setText(str(target_points))
                
                self.update_plot()
                QMessageBox.information(self, "Success", f"Loaded {data_count} points.")
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def update_plot(self):
        if self.waveform_data is None: return
        self.graph_widget.clear()
        
        # 1. 원본 데이터
        self.graph_widget.plot(self.waveform_data, pen=pg.mkPen('w', width=1, style=Qt.DashLine), name="Original CSV")
        
        # 2. 보간된 데이터 (UI 설정 포인트 수 기준)
        target_pts = self.points_slider.value()
        x_old = np.linspace(0, 1, len(self.waveform_data))
        x_new = np.linspace(0, 1, target_pts)
        resampled = np.interp(x_new, x_old, self.waveform_data)
        
        # 실제 장비로 전송될 포인트들을 시각화
        self.graph_widget.plot(np.linspace(0, len(self.waveform_data), target_pts), 
                               resampled, pen=pg.mkPen('y', width=1.5), 
                               symbol='o', symbolBrush='y', symbolSize=4, name=f"Resampled ({target_pts}pts)")
        self.graph_widget.setYRange(-1.1, 1.1)

    def apply_settings(self):
        if not self.inst:
            QMessageBox.warning(self, "Connect First", "Please connect to instrument.")
            return
        
        try:
            target_pts = self.points_slider.value()

            if self.waveform_data is not None:
                # 선택된 포인트 수로 보간
                x_old = np.linspace(0, 1, len(self.waveform_data))
                x_new = np.linspace(0, 1, target_pts)
                resampled = np.interp(x_new, x_old, self.waveform_data)
                
                # DAC 매핑 (-2047 to 2047)
                dac_data = np.clip(resampled * 2047, -2047, 2047).astype(np.int16)

                # 예상 소요 시간 계산 (2400bps 기준, 안전 계수 1.1 적용)
                self.expected_time = (target_pts * 2 / 240) * 1.1        
                self.elapsed_tick = 0
                # 1. 프로그레스 다이얼로그 설정
                self.pd = QProgressDialog(f"데이터 전송 중... (예상: {int(self.expected_time)}초)", None, 0, 100, self)
                self.pd.setWindowTitle("HP 33120A Transfer")
                self.pd.setWindowModality(Qt.WindowModal)
                self.pd.show()
                self.isWorkerFinished = False
                
                # 2. 메인 쓰레드 타이머 설정 (1초마다 UI 업데이트)
                self.ui_timer = QTimer(self)
                self.ui_timer.setInterval(1000)
                self.ui_timer.timeout.connect(self.update_transfer_progress)
                self.ui_timer.start() # 1000ms = 1s
                
                # 3. 워커 쓰레드 시작
                vpp = abs(float(self.volt_combo.currentText()))
                freq = self.freq_edit.text()
                offset = self.offset_edit.text()
                self.worker = TransferWorker(self.inst, dac_data, freq, vpp, offset)
                self.worker.finished.connect(self.on_transfer_finished)
                self.worker.start()

        except Exception as e: QMessageBox.critical(self, "Error", str(e))
    
    
    def update_transfer_progress(self):
        self.elapsed_tick += 1
        # 실제 진행률 계산 (95%까지만 자동으로 차오르게 함)
        progress_val = int((self.elapsed_tick / self.expected_time) * 95)
        if progress_val < 98:
            self.pd.setValue(progress_val)
            self.pd.setLabelText(f"전송 중... {self.elapsed_tick}초 / 약 {int(self.expected_time)}초")

    @pyqtSlot(bool, str)
    def on_transfer_finished(self, success, message):
        if hasattr(self, 'ui_timer'):
            self.ui_timer.stop()
        
        self.pd.setValue(100)
        print(f'Signal received: {success}, {message}')
        
        # 2. 결과 알림
        if success:
            QMessageBox.information(self, "Complete", "Waveform Applied Successfully!")
        else:
            QMessageBox.critical(self, "Error", f"Transfer failed: {message}")
        
        # 3. 다이얼로그 닫기 및 정리
        self.pd.close()
        self.worker.deleteLater() # 안전하게 쓰레드 객체 삭제
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SignalGeneratorGUI()
    window.show()
    sys.exit(app.exec_())