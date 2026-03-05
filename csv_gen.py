import numpy as np
import pandas as pd

# 설정: 1,000개의 데이터 포인트 (한 주기)
points = 200
t = np.linspace(0, 1, points, endpoint=False)

# 1. 사인파 (Sine Wave) 생성: -1 ~ 1 범위
sine_wave = (np.sin(2 * np.pi * t) * 2047).astype(int)

# 2. 사각파 (Square Wave) 생성: -1 ~ 1 범위 (Duty Cycle 50%)
# 0~0.5초까지는 1, 0.5~1초까지는 -1
square_wave = np.where(t < 0.5, 2047, -2047).astype(int)

# CSV 저장 (헤더 없이 데이터만 저장)
pd.DataFrame(sine_wave).to_csv('sine_test.csv', index=False, header=False)
pd.DataFrame(square_wave).to_csv('square_test.csv', index=False, header=False)

print("테스트용 CSV 파일 2개가 생성되었습니다: sine_test.csv, square_test.csv")