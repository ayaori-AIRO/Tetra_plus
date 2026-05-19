import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import random
import datetime
from pathlib import Path

# Firebase 인증
BASE_DIR = Path(__file__).resolve().parent
cred = credentials.Certificate(BASE_DIR / "react-test-542ec-firebase-adminsdk-fbsvc-66cefbc805.json")
firebase_admin.initialize_app(cred)

# Firestore 연결
db = firestore.client()

# 임의 검사 데이터 생성
data = {
    "extinguisher_id": "EXT" + str(random.randint(1, 50)),
    "location": random.choice(["1F", "2F", "3F"]),
    "pressure": random.choice(["normal", "low"]),
    "appearance": random.choice(["clean", "dirty"]),
    "result": random.choice(["pass", "fail"]),
    "time": str(datetime.datetime.now())
}

# Firestore에 저장
db.collection("inspection").add(data)

print("Firebase 전송 완료")
print(data)
