#!/usr/bin/env python3

import argparse
import json
import math
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import numpy as np

import corrosion_check
import label_paddleocr_onnx as label_ocr


INSPECTION_DIR = Path(__file__).resolve().parents[2]
CAPTURE_DIR = INSPECTION_DIR / "capture" / "inspection"
REACT_WEB_DIR = INSPECTION_DIR / "react" / "inspection-web"
REACT_PUBLIC_RESULT_DIR = REACT_WEB_DIR / "public" / "inspection-results"
REACT_BUILD_RESULT_DIR = REACT_WEB_DIR / "build" / "inspection-results"
FIREBASE_DIR = INSPECTION_DIR / "react" / "project"
FIREBASE_KEY = FIREBASE_DIR / "react-test-542ec-firebase-adminsdk-fbsvc-66cefbc805.json"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SAFE_ANGLE_MIN = 85
SAFE_ANGLE_MAX = 95
CORROSION_SIDE_COUNT = 4


def image_files(directory):
    if not directory.exists():
        return []
    return sorted(
        [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=lambda path: path.stat().st_mtime,
    )


def latest_image(directory):
    files = image_files(directory)
    return files[-1] if files else None


def latest_image_after(directory, timestamp):
    files = [
        path
        for path in image_files(directory)
        if path.stat().st_mtime >= timestamp
    ]
    return files[-1] if files else None


def ensure_result_dirs(result_dir):
    for subdir in ("fire_extinguisher", "pressure_gauge", "label", "full"):
        (result_dir / subdir).mkdir(parents=True, exist_ok=True)


def publish_result_image(local_path, result_dir):
    if not local_path or not Path(local_path).exists():
        return ""

    relative_path = Path(local_path).relative_to(CAPTURE_DIR)
    public_path = REACT_PUBLIC_RESULT_DIR / relative_path
    public_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(local_path, public_path)

    if (REACT_WEB_DIR / "build").exists():
        build_path = REACT_BUILD_RESULT_DIR / relative_path
        build_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, build_path)

    return f"/inspection-results/{relative_path.as_posix()}"


def run_corrosion_for_image(image_path, output_path):
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(image_path)

    body_mask, red_mask, _, _ = corrosion_check.build_red_body_mask(image)
    label_mask = corrosion_check.build_label_mask(image, body_mask)
    candidate_mask = corrosion_check.build_corrosion_color_mask(
        image,
        body_mask,
        red_mask,
        label_mask,
    )
    tile_mask, tile_rows = corrosion_check.inspect_tiles(
        image,
        candidate_mask,
        body_mask,
        tile_size=64,
        color_ratio_thresh=0.018,
        texture_thresh=18.0,
    )
    small_mask = corrosion_check.recover_small_candidates(
        candidate_mask,
        tile_mask,
        body_mask,
        image,
        small_area=12.0,
        texture_thresh=18.0,
    )
    final_candidate_mask = cv2.bitwise_or(tile_mask, small_mask)
    regions = corrosion_check.find_corrosion_regions(
        final_candidate_mask,
        body_mask,
        min_area=35.0,
        texture_thresh=18.0,
        image=image,
    )
    region_mask = corrosion_check.build_region_mask(final_candidate_mask.shape, regions)
    body_area = max(1, cv2.countNonZero(body_mask))
    corrosion_area = sum(region["area"] for region in regions)
    severity_ratio = corrosion_area / float(body_area) * 100.0
    output = corrosion_check.draw_result(
        image,
        body_mask,
        region_mask,
        tile_rows,
        regions,
        severity_ratio,
        show_tiles=False,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), output)
    return {
        "image": str(image_path),
        "output": str(output_path),
        "regions": len(regions),
        "severity_ratio": severity_ratio,
        "appearance": "부식" if regions else "정상",
    }


def inspect_corrosion(
    extinguisher_dir,
    result_dir,
    side_count=CORROSION_SIDE_COUNT,
    capture_started_at=None,
):
    fire_images = image_files(extinguisher_dir / "fire_extinguisher")
    if capture_started_at is not None:
        fire_images = [
            image_path
            for image_path in fire_images
            if image_path.stat().st_mtime >= capture_started_at
        ]
    if not fire_images:
        return {
            "appearance": "인식 안됨",
            "ok": False,
            "message": "fire_extinguisher 이미지 없음",
            "image": "",
            "sides": [],
            "checked_count": 0,
        }

    fire_images = fire_images[-side_count:]
    corrosion_result_dir = result_dir / "fire_extinguisher"
    for old_result in corrosion_result_dir.glob("corrosion_result_*.jpg"):
        old_result.unlink()

    side_results = []
    has_corrosion = False
    representative_image = ""
    for index, image_path in enumerate(fire_images, start=1):
        output_path = corrosion_result_dir / f"corrosion_result_{index:02d}.jpg"
        result = run_corrosion_for_image(image_path, output_path)
        result["side"] = index
        side_results.append(result)
        representative_image = representative_image or str(output_path)
        if result["appearance"] == "부식":
            has_corrosion = True

    return {
        "appearance": "부식" if has_corrosion else "정상",
        "ok": True,
        "message": "",
        "image": representative_image,
        "sides": side_results,
        "checked_count": len(side_results),
    }


def inspect_gauge(image_path, output_path):
    gauge_img = cv2.imread(str(image_path))
    if gauge_img is None:
        raise FileNotFoundError(image_path)

    h, w = gauge_img.shape[:2]
    gray_for_circle = cv2.cvtColor(gauge_img, cv2.COLOR_BGR2GRAY)
    gray_for_circle = cv2.medianBlur(gray_for_circle, 5)
    circles = cv2.HoughCircles(
        gray_for_circle,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min(w, h) // 2,
        param1=80,
        param2=20,
        minRadius=min(w, h) // 3,
        maxRadius=min(w, h) // 2,
    )

    detected_radius = min(w, h) // 2 - 5
    if circles is not None:
        circles = np.uint16(np.around(circles))
        x, y, r = circles[0][0]
        center = (int(x), int(y))
        detected_radius = int(r)
    else:
        center = (w // 2, h // 2)

    processing_radius = max(1, detected_radius - 5)
    circle_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(circle_mask, center, processing_radius, 255, -1)
    gauge_circle = cv2.bitwise_and(gauge_img, gauge_img, mask=circle_mask)

    hsv = cv2.cvtColor(gauge_circle, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, np.array([0, 10, 10]), np.array([40, 255, 255]))
    mask2 = cv2.inRange(hsv, np.array([140, 10, 10]), np.array([180, 255, 255]))
    red_mask = mask1 + mask2

    kernel = np.ones((5, 5), np.uint8)
    green_kernel = np.ones((3, 3), np.uint8)
    lower_green = np.array([22, 25, 25])
    upper_green = np.array([115, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    clean_green = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, green_kernel)
    clean_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

    green_contours, _ = cv2.findContours(clean_green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    safe_min = SAFE_ANGLE_MIN
    safe_max = SAFE_ANGLE_MAX
    if green_contours:
        largest_green = max(green_contours, key=cv2.contourArea)
        if cv2.contourArea(largest_green) > 30:
            angles = []
            for pt in largest_green.reshape(-1, 2):
                dx = pt[0] - center[0]
                dy = center[1] - pt[1]
                angle = math.degrees(math.atan2(dy, dx))
                if angle < 0:
                    angle += 360
                angles.append(angle)
            safe_min, safe_max = min(angles), max(angles)

    contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_result = gauge_img.copy()
    cv2.circle(img_result, center, max(1, detected_radius), (255, 255, 0), 1)
    cv2.circle(img_result, center, 2, (255, 255, 0), -1)

    tip_point = None
    current_angle = None
    decision_source = "NO_NEEDLE"
    pressure = "낮음"
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        pts = largest_contour.reshape(-1, 2)
        distances = np.sqrt((pts[:, 0] - center[0]) ** 2 + (pts[:, 1] - center[1]) ** 2)
        tip_point = tuple(pts[np.argmax(distances)])
        dx = tip_point[0] - center[0]
        dy = center[1] - tip_point[1]
        current_angle = math.degrees(math.atan2(dy, dx))
        if current_angle < 0:
            current_angle += 360

        is_safe_angle = safe_min <= current_angle <= safe_max
        is_safe_hsv = False
        for check_dist in (3, 5, 7, 9, 11):
            check_x = round(tip_point[0] + check_dist * math.cos(math.radians(current_angle)))
            check_y = round(tip_point[1] - check_dist * math.sin(math.radians(current_angle)))
            if 0 <= check_x < w and 0 <= check_y < h:
                y1 = max(0, check_y - 1)
                y2 = min(h, check_y + 2)
                x1 = max(0, check_x - 1)
                x2 = min(w, check_x + 2)
                if cv2.countNonZero(clean_green[y1:y2, x1:x2]) > 0:
                    is_safe_hsv = True
                    break

        if is_safe_hsv:
            pressure = "정상"
            decision_source = "HSV_MAIN"
        elif is_safe_angle:
            pressure = "정상"
            decision_source = "ANGLE_BACKUP"
        else:
            decision_source = "DANGER"

    line_color = (0, 220, 0) if pressure == "정상" else (0, 0, 255)
    if tip_point is not None:
        cv2.line(img_result, center, tip_point, line_color, 2)
        cv2.circle(img_result, tip_point, 2, (255, 0, 0), -1)

    status_text = f"PRESSURE {pressure}"
    if current_angle is not None:
        status_text += f" angle={current_angle:.1f}"
    status_text += f" ({decision_source})"
    cv2.putText(img_result, status_text, (5, max(20, h - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
    cv2.putText(img_result, status_text, (5, max(20, h - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, line_color, 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), img_result)
    return {
        "pressure": pressure,
        "angle": None if current_angle is None else float(current_angle),
        "decision_source": decision_source,
        "image": str(output_path),
    }


class LabelInspector:
    def __init__(self):
        providers = label_ocr.get_onnx_providers()
        self.det_session = label_ocr.ort.InferenceSession(
            str(label_ocr.ONNX_MODEL_DIR / "PP-OCRv5_server_det" / "inference.onnx"),
            providers=providers,
        )
        self.rec_session = label_ocr.ort.InferenceSession(
            str(label_ocr.ONNX_MODEL_DIR / "korean_PP-OCRv5_mobile_rec" / "inference.onnx"),
            providers=providers,
        )
        self.characters = label_ocr.load_character_list(
            label_ocr.ONNX_MODEL_DIR / "korean_PP-OCRv5_mobile_rec" / "inference.yml"
        )

    def inspect(self, image_path, output_path):
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(image_path)
        image = label_ocr.dewarp_label_image(image, -0.06)

        boxes, _ = label_ocr.detect_text_boxes(
            self.det_session,
            image,
            det_thresh=0.2,
            box_thresh=0.4,
            unclip_ratio=2.0,
        )
        crops = [label_ocr.crop_text_region(image, box) for box in boxes]
        rec_rows = label_ocr.recognize_crops(self.rec_session, crops, self.characters)
        rows = [(box, text, score) for box, (text, score) in zip(boxes, rec_rows) if text.strip()]
        full_text = " ".join(text for _, text, _ in rows)
        expiry_date = label_ocr.extract_expiry(full_text)
        status = label_ocr.judge_expiry_status(expiry_date)
        today = label_ocr.get_korea_today()

        expiry = {
            "정상": "내용연한 정상",
            "비정상": "내용연한 초과",
            "판정불가": "판정불가",
        }.get(status, "판정불가")

        output = label_ocr.draw_results(image, rows)
        output = label_ocr.draw_summary_ui(output, today, expiry_date, status)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), output)

        return {
            "expiry": expiry,
            "expiry_date": expiry_date or "",
            "text": full_text,
            "image": str(output_path),
        }


def send_to_firebase(data):
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY)
        firebase_admin.initialize_app(cred)

    db = firestore.client()
    db.collection("inspection").add(data)


def inspect_extinguisher(
    extinguisher_id,
    label_inspector,
    send_firebase=True,
    corrosion_side_count=CORROSION_SIDE_COUNT,
    run_id=None,
    capture_started_at=None,
):
    capture_dir = CAPTURE_DIR / extinguisher_id
    inspection_time = datetime.now(ZoneInfo("Asia/Seoul"))
    run_id = run_id or inspection_time.strftime("%Y%m%d_%H%M%S")
    result_dir = CAPTURE_DIR / f"{extinguisher_id}_inspection" / run_id
    ensure_result_dirs(result_dir)

    corrosion = inspect_corrosion(
        capture_dir,
        result_dir,
        side_count=corrosion_side_count,
        capture_started_at=capture_started_at,
    )

    if capture_started_at is None:
        gauge_image = latest_image(capture_dir / "pressure_gauge")
        label_image = latest_image(capture_dir / "label")
        full_image = latest_image(capture_dir / "full")
    else:
        gauge_image = latest_image_after(capture_dir / "pressure_gauge", capture_started_at)
        label_image = latest_image_after(capture_dir / "label", capture_started_at)
        full_image = latest_image_after(capture_dir / "full", capture_started_at)

    if gauge_image:
        gauge = inspect_gauge(gauge_image, result_dir / "pressure_gauge" / "gauge_result.jpg")
    else:
        gauge = {
            "pressure": "인식 안됨",
            "angle": None,
            "decision_source": "NO_IMAGE",
            "image": "",
        }

    if label_image:
        label = label_inspector.inspect(label_image, result_dir / "label" / "label_result.jpg")
    else:
        label = {
            "expiry": "인식 안됨",
            "expiry_date": "",
            "text": "",
            "image": "",
        }

    result = (
        "pass"
        if gauge["pressure"] == "정상"
        and corrosion["appearance"] == "정상"
        and label["expiry"] == "내용연한 정상"
        else "fail"
    )

    pressure_image_url = publish_result_image(gauge["image"], result_dir)
    appearance_side_urls = [
        publish_result_image(side.get("output", ""), result_dir)
        for side in corrosion.get("sides", [])
    ]
    appearance_image_url = appearance_side_urls[0] if appearance_side_urls else ""
    expiry_image_url = publish_result_image(label["image"], result_dir)
    full_image_url = publish_result_image(full_image, result_dir)
    appearance_sides = []
    for side, image_url in zip(corrosion.get("sides", []), appearance_side_urls):
        appearance_sides.append({
            "side": side.get("side"),
            "appearance": side.get("appearance"),
            "regions": side.get("regions"),
            "severity_ratio": side.get("severity_ratio"),
            "image": image_url,
        })

    data = {
        "extinguisher_id": extinguisher_id,
        "pressure": gauge["pressure"],
        "appearance": corrosion["appearance"],
        "expiry": label["expiry"],
        "expiry_date": label["expiry_date"],
        "result": result,
        "time": inspection_time.isoformat(timespec="seconds"),
        "run_id": run_id,
        "pressure_image": pressure_image_url,
        "appearance_image": appearance_image_url,
        "appearance_images": appearance_side_urls,
        "appearance_sides": appearance_sides,
        "expiry_image": expiry_image_url,
        "full_image": full_image_url,
        "capture_complete": bool(corrosion["ok"] and gauge_image and label_image),
    }

    (result_dir / "inspection_result.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if send_firebase:
        send_to_firebase(data)

    return data


def parse_args():
    parser = argparse.ArgumentParser(description="Run extinguisher inspection for id1/id2/id3 captures")
    parser.add_argument("--ids", nargs="+", default=["id1", "id2", "id3"])
    parser.add_argument("--no-firebase", action="store_true")
    parser.add_argument(
        "--run-id",
        default=None,
        help="Inspection result folder name. Defaults to current Korea timestamp.",
    )
    parser.add_argument(
        "--capture-started-at",
        type=float,
        default=None,
        help="Only use capture images saved at or after this Unix timestamp.",
    )
    parser.add_argument(
        "--corrosion-side-count",
        type=int,
        default=CORROSION_SIDE_COUNT,
        help="Number of latest fire_extinguisher images to use for corrosion inspection.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    label_inspector = LabelInspector()
    run_id = args.run_id or datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d_%H%M%S")
    results = []
    for extinguisher_id in args.ids:
        result = inspect_extinguisher(
            extinguisher_id,
            label_inspector,
            send_firebase=not args.no_firebase,
            corrosion_side_count=args.corrosion_side_count,
            run_id=run_id,
            capture_started_at=args.capture_started_at,
        )
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    print("inspection pipeline finished", flush=True)
    return results


if __name__ == "__main__":
    main()
