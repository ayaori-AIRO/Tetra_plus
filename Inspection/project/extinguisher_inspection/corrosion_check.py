from pathlib import Path
import argparse

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_TILE_SIZE = 64
DEFAULT_COLOR_RATIO = 0.018
DEFAULT_TEXTURE_THRESH = 8.0
DEFAULT_MIN_AREA = 190.0
DEFAULT_SMALL_AREA = 12.0


def fill_body_rows(red_mask, image_shape):
    body_mask = np.zeros(red_mask.shape, dtype=np.uint8)
    min_segment_width = max(12, int(image_shape[1] * 0.04))
    min_handle_width = max(5, int(image_shape[1] * 0.015))
    handle_limit_y = int(image_shape[0] * 0.25)

    for y in range(red_mask.shape[0]):
        xs = np.where(red_mask[y] > 0)[0]
        if xs.size < min_handle_width:
            continue

        if y < handle_limit_y:
            gaps = np.where(np.diff(xs) > 1)[0]
            starts = np.r_[0, gaps + 1]
            ends = np.r_[gaps, xs.size - 1]

            for start, end in zip(starts, ends):
                x1, x2 = int(xs[start]), int(xs[end])
                if x2 - x1 < min_handle_width:
                    continue
                cv2.line(body_mask, (x1, y), (x2, y), 255, 1)
            continue

        if xs.size < min_segment_width:
            continue
        x1, x2 = int(xs.min()), int(xs.max())
        if x2 - x1 < min_segment_width:
            continue
        cv2.line(body_mask, (x1, y), (x2, y), 255, 1)

    return body_mask


def detect_gauge_circle(image):
    h, w = image.shape[:2]
    roi_h = int(h * 0.32)
    gray = cv2.cvtColor(image[:roi_h], cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    min_radius = max(10, int(w * 0.045))
    max_radius = max(min_radius + 5, int(w * 0.18))
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(20, min_radius * 2),
        param1=80,
        param2=18,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    if circles is None:
        return None

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    best_circle = None
    best_score = None
    for cx, cy, radius in np.round(circles[0]).astype(int):
        if cy > roi_h or radius <= 0:
            continue

        circle_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(circle_mask, (cx, cy), radius, 255, -1)
        mean_s = cv2.mean(hsv[:, :, 1], mask=circle_mask)[0]
        center_score = abs(cx - (w * 0.5)) / float(w)
        height_score = cy / float(max(1, roi_h))
        color_score = mean_s / 255.0
        score = center_score + height_score * 0.35 + color_score * 0.45

        if best_score is None or score < best_score:
            best_score = score
            best_circle = (cx, cy, radius)

    return best_circle


def remove_gauge_circle(body_mask, image):
    circle = detect_gauge_circle(image)
    if circle is None:
        return body_mask

    cx, cy, radius = circle
    cleaned = body_mask.copy()
    cv2.circle(cleaned, (cx, cy), int(radius * 1.18), 0, -1)
    return cleaned


def build_red_body_mask(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red1 = cv2.inRange(hsv, np.array([0, 45, 35]), np.array([12, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([165, 45, 35]), np.array([180, 255, 255]))
    red_mask_before_morph = cv2.bitwise_or(red1, red2)
    body_mask_before_morph = fill_body_rows(red_mask_before_morph, image.shape)
    body_mask_before_morph = remove_gauge_circle(body_mask_before_morph, image)

    kernel = np.ones((3, 3), np.uint8)
    red_mask = cv2.morphologyEx(red_mask_before_morph, cv2.MORPH_OPEN, kernel)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    body_mask = fill_body_rows(red_mask, image.shape)

    body_mask = cv2.morphologyEx(body_mask, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    body_mask = cv2.erode(body_mask, np.ones((3, 3), np.uint8), iterations=1)
    body_mask = remove_gauge_circle(body_mask, image)
    return body_mask, red_mask_before_morph, body_mask_before_morph, red_mask_before_morph


def build_label_mask(image, body_mask):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    _, s, v = cv2.split(hsv)
    seed = ((s < 95) & (v > 115) & (body_mask > 0)).astype(np.uint8) * 255
    contours, _ = cv2.findContours(seed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    label_mask = np.zeros(seed.shape, dtype=np.uint8)

    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        if y < image.shape[0] * 0.22:
            continue
        if area < 500 or w < 25 or h < 12:
            continue
        cv2.drawContours(label_mask, [contour], -1, 255, -1)

    label_mask = cv2.morphologyEx(label_mask, cv2.MORPH_CLOSE, np.ones((31, 21), np.uint8))
    label_mask = cv2.dilate(label_mask, np.ones((13, 13), np.uint8), iterations=1)
    return label_mask


def build_corrosion_color_mask(image, body_mask, red_mask, label_mask):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # Printed corrosion samples appear as dark red-brown in this camera setup.
    rust_hue = ((h >= 0) & (h <= 6)) | ((h >= 174) & (h <= 179))
    rust_sample = rust_hue & (s >= 90) & (v >= 40) & (v <= 110)
    y_indices = np.indices(body_mask.shape)[0]
    below_handle = y_indices > int(body_mask.shape[0] * 0.16)
    in_body = (body_mask > 0) & (label_mask == 0) & below_handle

    mask = (rust_sample & in_body).astype(np.uint8) * 255
    mask = cv2.medianBlur(mask, 3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    return mask


def texture_score(gray, mask):
    if cv2.countNonZero(mask) == 0:
        return 0.0

    lap = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
    values = np.abs(lap)[mask > 0]
    if values.size == 0:
        return 0.0
    return float(np.mean(values))


def inspect_tiles(image, candidate_mask, body_mask, tile_size, color_ratio_thresh, texture_thresh):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = candidate_mask.shape
    tile_mask = np.zeros_like(candidate_mask)
    tile_rows = []

    for y in range(0, h, tile_size):
        for x in range(0, w, tile_size):
            y2 = min(h, y + tile_size)
            x2 = min(w, x + tile_size)
            body_tile = body_mask[y:y2, x:x2]
            body_pixels = cv2.countNonZero(body_tile)
            if body_pixels < tile_size * tile_size * 0.18:
                continue

            cand_tile = candidate_mask[y:y2, x:x2]
            cand_pixels = cv2.countNonZero(cand_tile)
            color_ratio = cand_pixels / float(body_pixels)
            if color_ratio < color_ratio_thresh:
                continue

            tex = texture_score(gray[y:y2, x:x2], cand_tile)
            if tex < texture_thresh:
                continue

            tile_mask[y:y2, x:x2] = cv2.bitwise_or(tile_mask[y:y2, x:x2], cand_tile)
            tile_rows.append((x, y, x2, y2, color_ratio, tex))

    return tile_mask, tile_rows


def touches_body_side(body_mask, x, y, w, h, margin=5):
    center_y = min(body_mask.shape[0] - 1, y + h // 2)
    body_xs = np.where(body_mask[center_y] > 0)[0]
    if body_xs.size == 0:
        return False

    body_left = int(body_xs.min())
    body_right = int(body_xs.max())
    return (x - body_left <= margin) or (body_right - (x + w - 1) <= margin)


def recover_small_candidates(candidate_mask, tile_mask, body_mask, image, small_area, texture_thresh):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    recovered = np.zeros_like(candidate_mask)
    contours, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < small_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        if cv2.countNonZero(tile_mask[y:y + h, x:x + w]) > 0:
            continue
        if touches_body_side(body_mask, x, y, w, h):
            continue

        component_mask = np.zeros(candidate_mask.shape, dtype=np.uint8)
        cv2.drawContours(component_mask, [contour], -1, 255, -1)
        tex = texture_score(gray[y:y + h, x:x + w], component_mask[y:y + h, x:x + w])
        if tex < texture_thresh * 1.1:
            continue

        cv2.drawContours(recovered, [contour], -1, 255, -1)

    return recovered


def find_corrosion_regions(tile_mask, body_mask, min_area, texture_thresh, image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    contours, _ = cv2.findContours(tile_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        if h == 0:
            continue

        aspect = w / float(h)
        fill_ratio = area / float(w * h)
        touches_body_edge = touches_body_side(body_mask, x, y, w, h)
        region_mask = np.zeros(tile_mask.shape, dtype=np.uint8)
        cv2.drawContours(region_mask, [contour], -1, 255, -1)
        tex = texture_score(gray[y:y + h, x:x + w], region_mask[y:y + h, x:x + w])

        inner_body_mask = cv2.erode(body_mask, np.ones((11, 11), np.uint8), iterations=1)
        region_pixels = max(1, cv2.countNonZero(region_mask))
        inner_pixels = cv2.countNonZero(cv2.bitwise_and(region_mask, inner_body_mask))
        inner_ratio = inner_pixels / float(region_pixels)

        is_long_band = aspect > 5.0 and h < image.shape[0] * 0.08
        is_edge_streak = touches_body_edge and h > w * 1.8 and area < 900
        is_edge_sliver = touches_body_edge and aspect < 0.30 and h > 45
        is_sparse_large_region = area > 500 and fill_ratio < 0.18
        is_edge_candidate = inner_ratio < 0.45 and area < 1200
        is_bottom_edge_speck = touches_body_edge and (y + h) > image.shape[0] * 0.84 and area < 800
        if is_long_band:
            continue
        if is_edge_streak:
            continue
        if is_edge_sliver:
            continue
        if is_sparse_large_region:
            continue
        if is_edge_candidate:
            continue
        if is_bottom_edge_speck:
            continue
        if tex < texture_thresh * 0.75:
            continue

        regions.append(
            {
                "box": (x, y, w, h),
                "area": float(area),
                "texture": tex,
                "fill_ratio": fill_ratio,
            }
        )

    return sorted(regions, key=lambda item: item["area"], reverse=True)


def draw_result(image, body_mask, candidate_mask, tile_rows, regions, severity_ratio, show_tiles=False):
    output = image.copy()
    overlay = output.copy()
    overlay[candidate_mask > 0] = (0, 180, 255)
    output = cv2.addWeighted(overlay, 0.35, output, 0.65, 0)

    body_contours, _ = cv2.findContours(body_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(output, body_contours, -1, (255, 180, 0), 2)

    if show_tiles:
        for x1, y1, x2, y2, _, _ in tile_rows:
            cv2.rectangle(output, (x1, y1), (x2, y2), (80, 220, 255), 1)

    for idx, region in enumerate(regions, start=1):
        x, y, w, h = region["box"]
        cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 255), 2)
        label = f"rust {idx}"
        cv2.putText(output, label, (x, max(20, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3)
        cv2.putText(output, label, (x, max(20, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)

    status = "CORROSION" if regions else "NORMAL"
    color = (0, 0, 255) if regions else (0, 220, 0)
    text = f"{status}  regions={len(regions)}  area={severity_ratio:.3f}%"
    cv2.putText(output, text, (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
    cv2.putText(output, text, (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return output


def build_region_mask(mask_shape, regions):
    region_mask = np.zeros(mask_shape, dtype=np.uint8)
    for region in regions:
        x, y, w, h = region["box"]
        region_mask[y:y + h, x:x + w] = 255
    return region_mask


def run_check(args):
    image_path = Path(args.image)
    if not image_path.is_absolute():
        image_path = BASE_DIR / image_path

    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(image_path)

    body_mask, red_mask, body_mask_before_morph, red_mask_before_morph = build_red_body_mask(image)
    label_mask = build_label_mask(image, body_mask)
    candidate_mask = build_corrosion_color_mask(image, body_mask, red_mask, label_mask)
    tile_mask, tile_rows = inspect_tiles(
        image,
        candidate_mask,
        body_mask,
        args.tile_size,
        args.color_ratio,
        args.texture_thresh,
    )
    small_mask = recover_small_candidates(
        candidate_mask,
        tile_mask,
        body_mask,
        image,
        args.small_area,
        args.texture_thresh,
    )
    final_candidate_mask = candidate_mask
    regions = find_corrosion_regions(final_candidate_mask, body_mask, args.min_area, args.texture_thresh, image)
    region_mask = build_region_mask(final_candidate_mask.shape, regions)

    body_area = max(1, cv2.countNonZero(body_mask))
    corrosion_area = sum(region["area"] for region in regions)
    severity_ratio = corrosion_area / float(body_area) * 100.0

    output = draw_result(image, body_mask, region_mask, tile_rows, regions, severity_ratio, args.show_tiles)

    print("=== corrosion check ===", flush=True)
    print(f"image: {image_path}", flush=True)
    print(f"body_area: {body_area}", flush=True)
    print(f"regions: {len(regions)}", flush=True)
    print(f"severity_ratio: {severity_ratio:.4f}%", flush=True)
    for idx, region in enumerate(regions, start=1):
        x, y, w, h = region["box"]
        print(
            f"region {idx}: box=({x},{y},{w},{h}), "
            f"area={region['area']:.1f}, texture={region['texture']:.2f}, "
            f"fill={region['fill_ratio']:.2f}",
            flush=True,
        )

    if not args.no_show:
        cv2.imshow("corrosion result", resize_for_display(output, args.display_scale))
        cv2.imshow("body mask before morphology", resize_for_display(body_mask_before_morph, args.display_scale))
        cv2.imshow("body mask after morphology", resize_for_display(body_mask, args.display_scale))
        cv2.imshow("candidate mask", resize_for_display(candidate_mask, args.display_scale))
        cv2.imshow("region mask", resize_for_display(region_mask, args.display_scale))
        if args.show_tiles:
            cv2.imshow("tile candidates", resize_for_display(tile_mask, args.display_scale))
            cv2.imshow("small candidates", resize_for_display(small_mask, args.display_scale))
        print("이미지 창을 닫으려면 아무 키나 누르세요.", flush=True)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def resize_for_display(image, scale):
    if scale == 1.0:
        return image
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def parse_args():
    parser = argparse.ArgumentParser(description="HSV + texture corrosion checker for fire extinguisher crops")
    parser.add_argument(
        "--image",
        default="/home/ayaori/ros2_ws/src/tetra/Inspection/capture/inspection/id3/full/fallback_camera1_top_camera2_bottom_20260528_025806.jpg",
    )
    parser.add_argument("--tile-size", type=int, default=DEFAULT_TILE_SIZE)
    parser.add_argument("--color-ratio", type=float, default=DEFAULT_COLOR_RATIO)
    parser.add_argument("--texture-thresh", type=float, default=DEFAULT_TEXTURE_THRESH)
    parser.add_argument("--min-area", type=float, default=DEFAULT_MIN_AREA)
    parser.add_argument("--small-area", type=float, default=DEFAULT_SMALL_AREA)
    parser.add_argument("--display-scale", type=float, default=0.6)
    parser.add_argument("--no-show", action="store_true")
    parser.add_argument("--show-tiles", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run_check(parse_args())
