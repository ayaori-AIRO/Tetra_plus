import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import random
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# Firebase 인증
BASE_DIR = Path(__file__).resolve().parent
cred = credentials.Certificate(BASE_DIR / "react-test-542ec-firebase-adminsdk-fbsvc-66cefbc805.json")
firebase_admin.initialize_app(cred)

# Firestore 연결
db = firestore.client()

pressure = random.choice(["정상", "낮음"])
appearance = random.choice(["정상", "부식"])
expiry = random.choice(["내용연한 정상", "내용연한 초과"])

# 임의 검사 데이터 생성
data = {
    "extinguisher_id": random.choice(["id1", "id2", "id3"]),
    "pressure": pressure,
    "appearance": appearance,
    "expiry": expiry,
    "expiry_date": random.choice(["2028-05", "2029-11", "2030-02"]),
    "result": "pass" if pressure == "정상" and appearance == "정상" and expiry == "내용연한 정상" else "fail",
    "time": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
    "pressure_image": "",
    "appearance_image": "",
    "appearance_images": [],
    "appearance_sides": [],
    "expiry_image": "",
}

# Firestore에 저장
db.collection("inspection").add(data)

print("Firebase 전송 완료")
print(data)
