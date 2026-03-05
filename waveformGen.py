import os
import sys
import numpy as np
#import pandas as pd
import csv
import serial.tools.list_ports
import pyqtgraph as pg  # 그래프 라이브러리 추가
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QComboBox, QSlider, QLineEdit, QPushButton, 
                             QLabel, QFileDialog, QMessageBox)
import time
from PyQt5.QtCore import Qt
import pyvisa       

"""
[BUILD CMD]
python -m nuitka --standalone --onefile --disable-console ^
--jobs=8 ^
--enable-plugin=pyqt5 ^
--output-dir=build_out ^
waveformGen.py
"""
#python -m nuitka --standalone --show-memory --show-progress --enable-plugin=pyqt5 --onefile waveformGen.py
class SignalGeneratorGUI(QMainWindow):
    MAX_POINTS = 63 

    def __init__(self):
        super().__init__()
        self.inst = None
        self.addr = None
        self.waveform_data = None
        self.initUI()
        self.rm = pyvisa.ResourceManager()

    def check_visa_status():
        try:
            from pyvisa import util
            # 현재 pyvisa가 어떤 드라이버를 보고 있는지 정보를 가져옵니다.
            info = util.get_debug_info()
            print(f"VISA Debug Info :{info}")
        except Exception as e:
            print(f"Error{e}")

    def wait_for_enter(msg):
        input(f"\n>>> [대기] {msg} (엔터를 치면 진행합니다...)")

    def initUI(self):
        self.setWindowTitle("HP 33120A - Waveform Visualizer")
        self.setGeometry(100, 100, 800, 600) # 그래프 공간을 위해 창 크기 확대
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget) # 좌측 컨트롤, 우측 그래프

        # --- 좌측 컨트롤 패널 ---
        control_panel = QVBoxLayout()
        
        # 포트 설정
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        port_layout.addWidget(self.port_combo)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_instrument)
        port_layout.addWidget(self.btn_connect)
        control_panel.addLayout(port_layout)

        # 전압 설정
        control_panel.addWidget(QLabel("Peak Voltage (V):"))
        self.volt_combo = QComboBox()
        volts = [str(round(x * 0.5, 1)) for x in range(-10, 11) if x != 0]
        self.volt_combo.addItems(volts)
        self.volt_combo.setCurrentText("3.0") 
        control_panel.addWidget(self.volt_combo)

        # 오프셋 설정
        control_panel.addWidget(QLabel("Offset (VDC):"))
        self.offset_edit = QLineEdit("0.0")
        control_panel.addWidget(self.offset_edit)

        # 주파수 설정
        control_panel.addWidget(QLabel("Frequency (Hz):"))
        self.freq_edit = QLineEdit("1000")
        control_panel.addWidget(self.freq_edit)
        self.freq_slider = QSlider(Qt.Horizontal)
        self.freq_slider.setRange(1, 10000) 
        self.freq_slider.setValue(1000)
        control_panel.addWiget(self.freq_slider) if hasattr(control_panel, 'addWiget') else control_panel.addWidget(self.freq_slider)

        # 버튼들
        self.btn_load_csv = QPushButton("1. Load CSV")
        self.btn_load_csv.setMinimumHeight(40)
        self.btn_load_csv.clicked.connect(self.load_csv)
        control_panel.addWidget(self.btn_load_csv)

        self.btn_apply = QPushButton("2. Apply & Output")
        self.btn_apply.setMinimumHeight(60)
        self.btn_apply.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold;")
        self.btn_apply.clicked.connect(self.apply_settings)
        control_panel.addWidget(self.btn_apply)
        
        control_panel.addStretch() # 아래쪽 공백 채우기
        main_layout.addLayout(control_panel, 1)

        # --- 우측 그래프 패널 ---
        self.graph_widget = pg.PlotWidget()
        self.graph_widget.setBackground('k') # 배경 검은색
        self.graph_widget.showGrid(x=True, y=True)
        self.graph_widget.setLabel('left', 'Normalized Value', units='-1 to 1')
        self.graph_widget.setLabel('bottom', 'Points')
        self.graph_widget.addLegend() # 범례 추가
        main_layout.addWidget(self.graph_widget, 3) # 그래프 비중 확대

        # 슬라이더 동기화
        self.freq_slider.valueChanged.connect(lambda v: self.freq_edit.setText(str(v)))
        self.freq_edit.editingFinished.connect(lambda: self.freq_slider.setValue(int(float(self.freq_edit.text() or 1))))

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
            self.inst.data_bits = 8
            self.inst.read_termination = '\n'
            self.inst.write_termination = '\n'
            self.inst.timeout = 10000 # 10초로 넉넉히 설정
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
                #df = pd.read_csv(fname)    #판다스 용량 이슈
                with open(fname, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    self.waveform_data = np.array([float(row['Data']) for row in reader])
                    self.update_plot() # 그래프 업데이트
                
                QMessageBox.warning(self, "Success", "Loaded CSV data")
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def update_plot(self):
        """불러온 데이터를 그래프에 표시"""
        if self.waveform_data is None: return
        
        self.graph_widget.clear()
        
        # 1. 원본 데이터 (Raw) - 흰색 선
        self.graph_widget.plot(self.waveform_data, pen=pg.mkPen('w', width=1), name="Original CSV")
        
        # 2. 리샘플링된 데이터 (63pts) - 노란색 점/선
        # 장비로 실제 전송되는 형태를 시각적으로 보여줌
        x_old = np.linspace(0, len(self.waveform_data)-1, len(self.waveform_data))
        x_new = np.linspace(0, len(self.waveform_data)-1, self.MAX_POINTS)
        resampled = np.interp(x_new, x_old, self.waveform_data)
        
        self.graph_widget.plot(x_new, resampled, pen=None, symbol='o', symbolBrush='y', symbolSize=5, name="To Instrument (63pts)")
        
        # Y축 범위 고정 (-1.1 to 1.1)
        self.graph_widget.setYRange(-1.1, 1.1)

    def apply_settings(self):
        if not self.inst: return
        try:
            if self.waveform_data is not None:
                # 63포인트 보간 및 DAC 매핑
                x_old = np.linspace(0, 1, len(self.waveform_data))
                x_new = np.linspace(0, 1, self.MAX_POINTS)
                resampled = np.interp(x_new, x_old, self.waveform_data)
                dac_data = np.clip(resampled * 2047, -2047, 2047).astype(np.int16)
                print(dac_data)
                self.inst.clear()
                self.inst.write("*CLS")
                time.sleep(0.5)
                self.inst.write_binary_values("DATA:DAC VOLATILE, ", dac_data, datatype='h', is_big_endian=True)
                time.sleep(1.5) 

            #vpp = abs(float(self.volt_combo.currentText())) * 2
            vpp = abs(float(self.volt_combo.currentText()))
            freq = self.freq_edit.text()
            offset = self.offset_edit.text()
            
            user_data = f'APPLy:USER {freq}, {vpp}, {offset}'
            print(f'user_data = {user_data}')
            self.inst.write(user_data)
            time.sleep(0.5)
            self.inst.write("FUNC:USER VOLATILE")
            QMessageBox.information(self, "Complete", "Waveform Applied!")

        except Exception as e: QMessageBox.critical(self, "Error", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SignalGeneratorGUI()
    window.show()
    sys.exit(app.exec_())