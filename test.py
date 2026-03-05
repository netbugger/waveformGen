import sys
import os
import numpy as np
#import pandas as pd
import csv
import pyvisa      
import time 


def wait_for_enter(msg):
    input(f"\n>>> [대기] {msg} (엔터를 치면 진행합니다...)")
MAX_POINTS = 10
CHUNK_SIZE = 20
ADDR = "ASRL6::INSTR"
rm = pyvisa.ResourceManager()
from pyvisa import util
try:
    info = util.get_debug_info()
    print(f"VISA Debug Info :{info}")
except Exception as e:
    print(f"Error{e}")

try:
    inst = rm.open_resource(ADDR)
except Exception as e: print("Error", str(e))

inst.baud_rate = 2400
inst.data_bits = 8
inst.read_termination = '\n'
inst.write_termination = '\n'
inst.timeout = 100000 # 10초로 넉넉히 설정
idn = inst.query("*IDN?")
print(f'{idn.strip()}')

raw_points = np.array([2047]*1000 + [-2047]*1000, dtype=np.int16)
#raw_points = np.array([2047]*1000 + [0]*1000, dtype=np.int16)

                
                
                
inst.clear()
inst.write("*CLS")
time.sleep(0.5)
def write_binary_with_delay(values, chunk_size=60, delay=0.05):
    """
    values: -2047 ~ 2047 사이의 정수 리스트 또는 numpy 배열
    chunk_size: 한 번에 보낼 바이트 수 (33120A는 128~256 권장)
    delay: 각 청크 전송 사이의 시간 (초)
    """
    # 1. 데이터를 Big-endian 2-byte 정수로 변환
    # HP 33120A: DATA:DAC VOLATILE, <header><binary_data>
    data_bytes = np.array(raw_points, dtype='>i2').tobytes()
        
    # 2. IEEE 488.2 바이너리 헤더 생성 (#<n><digits><data>)
    byte_count = len(data_bytes)
    header = f"#{len(str(byte_count))}{byte_count}"
        
    # 3. 전체 명령 문자열의 시작 부분 전송
    # 33120A는 명령어와 데이터 사이에 공백이나 콤마가 필요할 수 있습니다.
    start_cmd = f"DATA:DAC VOLATILE, {header}".encode('ascii')
    inst.write_raw(start_cmd)
        
    # 4. 데이터 쪼개서 보내기 (핵심)
    for i in range(0, len(data_bytes), chunk_size):
        chunk = data_bytes[i:i + chunk_size]
        inst.write_raw(chunk)
        # 장비 버퍼가 비워질 시간을 줌
        time.sleep(delay)
            
    # 5. 종료 문자 전송
    inst.write_raw(b'\n')

def write_binary_with_raw(values):
    """
    values: -2047 ~ 2047 사이의 정수 리스트 또는 numpy 배열
    chunk_size: 한 번에 보낼 바이트 수 (33120A는 128~256 권장)
    delay: 각 청크 전송 사이의 시간 (초)
    """
    # 1. 데이터를 Big-endian 2-byte 정수로 변환
    # HP 33120A: DATA:DAC VOLATILE, <header><binary_data>
    data_bytes = np.array(raw_points, dtype='>i2').tobytes()
        
    # 2. IEEE 488.2 바이너리 헤더 생성 (#<n><digits><data>)
    byte_count = len(data_bytes)
    header = f"#{len(str(byte_count))}{byte_count}"
        
    # 3. 전체 명령 문자열의 시작 부분 전송
    # 33120A는 명령어와 데이터 사이에 공백이나 콤마가 필요할 수 있습니다.
    start_cmd = f"DATA:DAC VOLATILE, {header}".encode('ascii')
    print(f'header={start_cmd}')
    inst.write_raw(start_cmd)
        
    # Data Write
    inst.write_raw(data_bytes)
            
    # 5. 종료 문자 전송
    inst.write_raw(b'\n')
    
#write_binary_with_raw(raw_points)                
#write_binary_with_delay(raw_points, chunk_size=10, delay=0.05)
inst.write_binary_values("DATA:DAC VOLATILE, ", raw_points, datatype='h', is_big_endian=True)
time.sleep(0.2)
inst.write("FUNC:USER VOLATILE")
time.sleep(0.2)
user_data = f'APPLy:USER 1000, 6.0, 0.0'
print(f'user_data = {user_data}')
inst.write(user_data)
time.sleep(0.5)