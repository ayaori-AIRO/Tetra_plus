import argparse
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import numpy as np
import onnxruntime as ort
import pyclipper
import yaml


INSPECTION_DIR = Path(__file__).resolve().parents[2]
ONNX_MODEL_DIR = INSPECTION_DIR / "onnx_models"


def normalize_ocr_text(text):
    return re.sub(r"\s+", "", text)


def extract_expiry(text):
    text = normalize_ocr_text(text)
    patterns = [
        r"(20\d{2})년(\d{1,2})월",
        r"(20\d{2})[./-](\d{1,2})",
        r"(20\d{2})(0[1-9]|1[0-2])",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        year, month = match.groups()
        month = int(month)
        if 1 <= month <= 12:
            return f"{int(year):04d}-{month:02d}"
    return None


def get_korea_today():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def judge_expiry_status(expiry, today=None):
    if not expiry:
        return "판정불가"

    year, month = map(int, expiry.split("-"))
    today = today or get_korea_today()
    if (year, month) < (today.year, today.month):
        return "비정상"
    return "정상"


def resize_det_image(image, resize_long=960):
    h, w = image.shape[:2]
    ratio = float(resize_long) / max(h, w)
    resize_h = int(h * ratio)
    resize_w = int(w * ratio)
    stride = 128
    resize_h = max(stride, int(math.ceil(resize_h / stride) * stride))
    resize_w = max(stride, int(math.ceil(resize_w / stride) * stride))
    resized = cv2.resize(image, (resize_w, resize_h))
    return resized, np.array([h, w, resize_h / float(h), resize_w / float(w)])


def normalize_det_image(image):
    image = image.astype("float32") / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    image = (image - mean) / std
    image = image.transpose(2, 0, 1)
    return image[np.newaxis, :]


def get_mini_boxes(contour):
    bounding_box = cv2.minAreaRect(contour)
    points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])

    if points[1][1] > points[0][1]:
        index_1, index_4 = 0, 1
    else:
        index_1, index_4 = 1, 0

    if points[3][1] > points[2][1]:
        index_2, index_3 = 2, 3
    else:
        index_2, index_3 = 3, 2

    box = [points[index_1], points[index_2], points[index_3], points[index_4]]
    return box, min(bounding_box[1])


def box_score_fast(bitmap, box):
    h, w = bitmap.shape[:2]
    box = box.copy()
    xmin = max(0, min(math.floor(box[:, 0].min()), w - 1))
    xmax = max(0, min(math.ceil(box[:, 0].max()), w - 1))
    ymin = max(0, min(math.floor(box[:, 1].min()), h - 1))
    ymax = max(0, min(math.ceil(box[:, 1].max()), h - 1))
    mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
    box[:, 0] -= xmin
    box[:, 1] -= ymin
    cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
    return cv2.mean(bitmap[ymin:ymax + 1, xmin:xmax + 1], mask)[0]


def unclip(box, unclip_ratio):
    area = cv2.contourArea(box)
    length = cv2.arcLength(box, True)
    if length == 0:
        return np.array([])
    distance = area * unclip_ratio / length
    offset = pyclipper.PyclipperOffset()
    offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    expanded = offset.Execute(distance)
    if not expanded:
        return np.array([])
    return np.array(expanded)


def boxes_from_bitmap(pred, bitmap, dest_width, dest_height, box_thresh=0.6, unclip_ratio=1.5):
    height, width = bitmap.shape
    width_scale = dest_width / width
    height_scale = dest_height / height
    contours, _ = cv2.findContours(
        (bitmap * 255).astype(np.uint8),
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    boxes = []
    scores = []
    for contour in contours[:1000]:
        points, sside = get_mini_boxes(contour)
        if sside < 3:
            continue
        points = np.array(points)
        score = box_score_fast(pred, points.reshape(-1, 2))
        if score < box_thresh:
            continue

        expanded = unclip(points, unclip_ratio)
        if expanded.size == 0:
            continue
        expanded = expanded.reshape(-1, 1, 2)
        box, sside = get_mini_boxes(expanded)
        if sside < 5:
            continue

        box = np.array(box)
        box[:, 0] = np.clip(np.round(box[:, 0] * width_scale), 0, dest_width)
        box[:, 1] = np.clip(np.round(box[:, 1] * height_scale), 0, dest_height)
        boxes.append(box.astype(np.int16))
        scores.append(score)

    return boxes, scores


def detect_text_boxes(det_session, image, det_thresh=0.3, box_thresh=0.6, unclip_ratio=1.5):
    resized, shape = resize_det_image(image)
    det_input = normalize_det_image(resized)
    input_name = det_session.get_inputs()[0].name
    pred = det_session.run(None, {input_name: det_input})[0][0]
    pred_map = pred[0]
    bitmap = pred_map > det_thresh
    src_h, src_w = int(shape[0]), int(shape[1])
    boxes, scores = boxes_from_bitmap(
        pred_map,
        bitmap,
        src_w,
        src_h,
        box_thresh=box_thresh,
        unclip_ratio=unclip_ratio,
    )
    return sort_boxes(boxes), scores


def order_points_clockwise(points):
    points = np.asarray(points, dtype=np.float32)
    x_sorted = points[np.argsort(points[:, 0]), :]
    left = x_sorted[:2, :]
    right = x_sorted[2:, :]
    left = left[np.argsort(left[:, 1]), :]
    right = right[np.argsort(right[:, 1]), :]
    return np.array([left[0], right[0], right[1], left[1]], dtype=np.float32)


def crop_text_region(image, box):
    box = order_points_clockwise(box)
    width_top = np.linalg.norm(box[0] - box[1])
    width_bottom = np.linalg.norm(box[3] - box[2])
    height_left = np.linalg.norm(box[0] - box[3])
    height_right = np.linalg.norm(box[1] - box[2])
    crop_w = max(1, int(max(width_top, width_bottom)))
    crop_h = max(1, int(max(height_left, height_right)))

    dst = np.array(
        [[0, 0], [crop_w, 0], [crop_w, crop_h], [0, crop_h]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(box, dst)
    return cv2.warpPerspective(image, matrix, (crop_w, crop_h), borderMode=cv2.BORDER_REPLICATE)


def resize_rec_image(image, img_h=48, img_w=320):
    h, w = image.shape[:2]
    ratio = w / float(h)
    resized_w = min(img_w, int(math.ceil(img_h * ratio)))
    resized = cv2.resize(image, (resized_w, img_h))
    resized = resized.astype("float32").transpose(2, 0, 1) / 255.0
    resized = (resized - 0.5) / 0.5
    padded = np.zeros((3, img_h, img_w), dtype=np.float32)
    padded[:, :, :resized_w] = resized
    return padded


def load_character_list(rec_yml_path):
    data = yaml.safe_load(open(rec_yml_path, "r", encoding="utf-8"))
    chars = data["PostProcess"]["character_dict"]
    return ["blank"] + chars + [" "]


def ctc_decode(preds, characters):
    idxs = preds.argmax(axis=-1)
    probs = preds.max(axis=-1)
    texts = []
    scores = []
    for idx_seq, prob_seq in zip(idxs, probs):
        chars = []
        confs = []
        last_idx = None
        for idx, prob in zip(idx_seq, prob_seq):
            idx = int(idx)
            if idx == 0 or idx == last_idx:
                last_idx = idx
                continue
            if idx < len(characters):
                chars.append(characters[idx])
                confs.append(float(prob))
            last_idx = idx
        text = unicodedata.normalize("NFC", "".join(chars))
        score = float(np.mean(confs)) if confs else 0.0
        texts.append(text)
        scores.append(score)
    return texts, scores


def recognize_crops(rec_session, crops, characters):
    rows = []
    input_name = rec_session.get_inputs()[0].name
    for crop in crops:
        rec_input = resize_rec_image(crop)[np.newaxis, :]
        pred = rec_session.run(None, {input_name: rec_input})[0]
        texts, scores = ctc_decode(pred, characters)
        rows.append((texts[0], scores[0]))
    return rows


def get_onnx_providers():
    available = ort.get_available_providers()
    preferred = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return [provider for provider in preferred if provider in available]


def sort_boxes(boxes):
    return sorted(boxes, key=lambda box: (np.min(box[:, 1]), np.min(box[:, 0])))


def draw_results(image, rows):
    output = image.copy()
    for box, text, score in rows:
        cv2.polylines(output, [box.astype(np.int32)], True, (0, 180, 0), 2)
        x, y = int(np.min(box[:, 0])), int(np.min(box[:, 1]))
        label = f"{text} {score:.2f}"
        cv2.putText(output, label, (x, max(18, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 120, 0), 1)
    return output


def draw_summary_ui(image, today, expiry, status):
    panel_h = 96
    min_width = 720
    right_pad = max(0, min_width - image.shape[1])
    output = cv2.copyMakeBorder(image, panel_h, 0, 0, right_pad, cv2.BORDER_CONSTANT, value=(245, 245, 245))
    status_text = {
        "정상": "NORMAL",
        "비정상": "EXPIRED",
        "판정불가": "UNKNOWN",
    }.get(status, "UNKNOWN")
    status_color = {
        "정상": (35, 145, 60),
        "비정상": (30, 30, 220),
        "판정불가": (80, 80, 80),
    }.get(status, (80, 80, 80))

    cv2.putText(output, f"Today(KST): {today.isoformat()}", (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (30, 30, 30), 2)
    cv2.putText(output, f"Extinguisher expiry: {expiry if expiry else 'not found'}", (18, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (30, 30, 30), 2)
    cv2.putText(output, f"Status: {status_text}", (18, 91), cv2.FONT_HERSHEY_SIMPLEX, 0.75, status_color, 2)
    return output


def resize_for_display(image, scale):
    if scale == 1.0:
        return image
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image",
        default="/home/ayaori/ros2_ws/src/tetra/Inspection/capture/inspection/label/camera1_20260524_012222_96.jpg",
    )
    parser.add_argument(
        "--det-model",
        default=str(ONNX_MODEL_DIR / "PP-OCRv5_server_det" / "inference.onnx"),
    )
    parser.add_argument(
        "--rec-model",
        default=str(ONNX_MODEL_DIR / "korean_PP-OCRv5_mobile_rec" / "inference.onnx"),
    )
    parser.add_argument(
        "--rec-yml",
        default=str(ONNX_MODEL_DIR / "korean_PP-OCRv5_mobile_rec" / "inference.yml"),
    )
    parser.add_argument("--det-thresh", type=float, default=0.2)
    parser.add_argument("--box-thresh", type=float, default=0.4)
    parser.add_argument("--unclip", type=float, default=2.0)
    parser.add_argument("--display-scale", type=float, default=1.0)
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()

    image = cv2.imread(str(Path(args.image)))
    if image is None:
        raise FileNotFoundError(args.image)

    providers = get_onnx_providers()
    print(f"ONNX Runtime providers: {providers}", flush=True)
    det_session = ort.InferenceSession(args.det_model, providers=providers)
    rec_session = ort.InferenceSession(args.rec_model, providers=providers)
    characters = load_character_list(args.rec_yml)

    boxes, _ = detect_text_boxes(
        det_session,
        image,
        det_thresh=args.det_thresh,
        box_thresh=args.box_thresh,
        unclip_ratio=args.unclip,
    )
    crops = [crop_text_region(image, box) for box in boxes]
    rec_rows = recognize_crops(rec_session, crops, characters)
    rows = [(box, text, score) for box, (text, score) in zip(boxes, rec_rows) if text.strip()]
    full_text = " ".join(text for _, text, _ in rows)
    expiry = extract_expiry(full_text)
    today = get_korea_today()
    status = judge_expiry_status(expiry, today)

    print("=== ONNX OCR detected text ===", flush=True)
    print(
        f"det_thresh={args.det_thresh}, box_thresh={args.box_thresh}, unclip={args.unclip}, boxes={len(boxes)}",
        flush=True,
    )
    if not rows:
        print("not found", flush=True)
    for _, text, score in rows:
        print(f"{text}\t(score: {score:.3f})", flush=True)

    print("=== Full extracted text ===", flush=True)
    print(full_text if full_text else "not found", flush=True)
    print("=== Extracted expiry ===", flush=True)
    print(expiry if expiry else "not found", flush=True)
    print("=== Current date (KST) ===", flush=True)
    print(today.isoformat(), flush=True)
    print("=== Expiry status ===", flush=True)
    print(status, flush=True)

    if not args.no_show:
        output = draw_results(image, rows)
        output = draw_summary_ui(output, today, expiry, status)
        display = resize_for_display(output, args.display_scale)
        cv2.namedWindow("onnx ocr result", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("onnx ocr result", display.shape[1], display.shape[0])
        cv2.imshow("onnx ocr result", display)
        print("이미지 창을 닫으려면 아무 키나 누르세요.", flush=True)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
