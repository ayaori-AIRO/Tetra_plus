# run_paddleocr_venv_test.py
import subprocess
import sys

# 1️⃣ 가상환경 Python 경로
venv_python = "/home/ayaori/paddle_cpu_env/bin/python"

# 2️⃣ PaddleOCR 스크립트 경로
script_path = "/home/ayaori/Capstone/project/label_paddleOCR.py"

# 3️⃣ 테스트용 이미지
img_path = "/home/ayaori/Capstone/capture/label_crop.jpg"

# 4️⃣ subprocess로 가상환경에서 PaddleOCR 실행
# ROI 필요 없으면 img_path만 전달
result = subprocess.run([venv_python, script_path, img_path], capture_output=True, text=True)

# 5️⃣ 실행 결과 확인
if result.returncode != 0:
    print("PaddleOCR 실행 오류")
    print(result.stderr)
else:
    print("PaddleOCR 실행 완료")
    print(result.stdout)