import pyvisa
import numpy as np
import time

# 1. 장비 연결 설정
rm = pyvisa.ResourceManager()
# Connection Expert에서 확인한 주소를 입력하세요 (예: 'ASRL3::INSTR')
inst = rm.open_resource('ASRL6::INSTR')

# RS-232 통신 설정 (장비 설정과 일치해야 함)
inst.baud_rate = 9600
inst.data_bits = 8
inst.parity = pyvisa.constants.Parity.none
inst.stop_bits = pyvisa.constants.StopBits.one
inst.termination = '\n'

try:
    # 2. 장비 초기화 및 연결 확인
    print("연결 확인:", inst.query("*IDN?"))
    
    # 3. -3V ~ +3V 신호를 위한 파형 데이터 생성
    # 예: 100개의 포인트로 이루어진 사인파
    t = np.linspace(0, 2*np.pi, 20)
    # -2047 ~ 2047 범위로 스케일링 (정수형)
    waveform_points = (np.sin(t) * 2047).astype(int)
    
    # 데이터를 문자열로 변환 (예: "0, 500, 2047, ...")
    data_str = ",".join(map(str, waveform_points))
    
    # 4. 장비로 명령 전송
    # 메모리에 데이터 다운로드 (VOLATILE 영역)
    inst.write(f"DATA VOLATILE, {data_str}")
    
    # 파형 선택
    inst.write("FUNC:USER VOLATILE")
    time.sleep(0.2)
    user_data = f'APPLy:USER 1000, 6.0, 0.0'
    print(f'user_data = {user_data}')
    inst.write(user_data)
    time.sleep(0.5)
    
    print("전송 완료: -3V ~ +3V 범위의 신호가 출력 중입니다.")

except Exception as e:
    print(f"오류 발생: {e}")

finally:
    inst.close()