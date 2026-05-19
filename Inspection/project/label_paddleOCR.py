import re
import cv2
from paddleocr import PaddleOCR

def preprocess_image(img_path, roi=None):
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {img_path}")

    # ================================
    # 1️⃣ 원본
    # ================================
    cv2.imshow("1_original", cv2.resize(img, None, fx=0.6, fy=0.6))

    if roi:
        x1, y1, x2, y2 = roi
        img = img[y1:y2, x1:x2]
        cv2.imshow("2_roi", cv2.resize(img, None, fx=0.6, fy=0.6))

    # ================================
    # 3️⃣ Grayscale
    # ================================
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cv2.imshow("3_gray", cv2.resize(gray, None, fx=0.6, fy=0.6))

    # ================================
    # 4️⃣ Blur
    # ================================
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    cv2.imshow("4_blur", cv2.resize(gray, None, fx=0.6, fy=0.6))

    # ================================
    # 5️⃣ Threshold (Otsu)
    # ================================
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cv2.imshow("5_threshold", cv2.resize(thresh, None, fx=0.6, fy=0.6))

    return thresh


def ocr_multi_lang(img):
    ocr_en = PaddleOCR(use_angle_cls=True, use_textline_orientation=True, lang='en', use_gpu=False)
    ocr_ko = PaddleOCR(use_angle_cls=True, use_textline_orientation=True, lang='korean', use_gpu=False)

    result_en = ocr_en.ocr(img, cls=True)
    result_ko = ocr_ko.ocr(img, cls=True)

    combined_results = []
    for line in result_en[0] + result_ko[0]:
        combined_results.append(line)

    # y 기준 정렬
    combined_results.sort(key=lambda x: (x[0][0][1], x[0][0][0]))

    return combined_results


def extract_year_month_from_ocr(results):
    year = None
    month = None

    for line in results:
        text = line[1][0]

        match_year = re.search(r'(\d{4})\s*년', text)
        if match_year:
            year = match_year.group(1)

        match_month = re.search(r'(\d{2})\s*월', text)
        if match_month:
            month = match_month.group(1)

    if year and month:
        return f"{year}-{month}"
    else:
        return None


if __name__ == "__main__":
    img_path = "/home/ayaori/Capstone/capture/label_crop.jpg"

    processed_img = preprocess_image(img_path)

    # ================================
    # OCR 실행
    # ================================
    results = ocr_multi_lang(processed_img)

    print("=== OCR Results ===")
    for line in results:
        print(f"Detected text: '{line[1][0]}' with confidence: {line[1][1]:.2f}")

    extracted_date = extract_year_month_from_ocr(results)

    if extracted_date:
        print("📅 추출된 날짜:", extracted_date)
    else:
        print("⚠️ 날짜 정보를 찾지 못했습니다.")

    cv2.waitKey(0)
    cv2.destroyAllWindows()