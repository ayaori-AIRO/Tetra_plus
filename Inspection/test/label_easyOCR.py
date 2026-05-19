import re
import cv2
import easyocr

def preprocess_image_steps(img_path, roi=None):
    """
    이미지 전처리: Grayscale -> CLAHE -> Blur
    """
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {img_path}")

    if roi is not None:
        x1, y1, x2, y2 = roi
        img = img[y1:y2, x1:x2]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_clahe = clahe.apply(gray)
    blurred = cv2.GaussianBlur(gray_clahe, (3, 3), 0)

    return blurred

def ocr_easyocr(img):
    """
    EasyOCR로 OCR 수행 (한국어+영어+숫자)
    """
    reader = easyocr.Reader(['ko','en'], gpu=False)
    result = reader.readtext(img)
    return result

def extract_manufacture_date(ocr_results):
    """
    OCR 결과에서 제조연월 추출
    - 'xxxx년 xx월' 패턴에 맞는 텍스트만 필터링
    """
    pattern = r'(\d{4})\s*년\s*(\d{1,2})\s*월'
    for _, text, conf in ocr_results:
        match = re.search(pattern, text)
        if match:
            year, month = match.groups()
            return f"{year}년 {month}월"
    return None

if __name__ == "__main__":
    img_path = "/home/ayaori/Capstone/capture/label_crop.jpg"
    roi_coords = None  # ROI 지정 가능

    # 1️⃣ 전처리
    processed_img = preprocess_image_steps(img_path, roi=roi_coords)

    # 2️⃣ OCR 수행
    results = ocr_easyocr(processed_img)

    # 3️⃣ 제조연월 추출
    manufacture_date = extract_manufacture_date(results)

    # 결과 출력
    print("=== EasyOCR Results ===")
    for _, text, confidence in results:
        print(f"Detected text: '{text}' (conf: {confidence:.2f})")

    if manufacture_date:
        print(f"✅ 제조연월 추출됨: {manufacture_date}")
    else:
        print("❌ 제조연월을 찾지 못함")