"""Four-quadrant pixel displacement and dated time-series analysis."""
from datetime import date
import cv2
import numpy as np
from .matching import consistent_matches

REGIONS = [("region1", "左上"), ("region2", "右上"),
           ("region3", "左下"), ("region4", "右下")]


def quadrants(image):
    h, w = image.shape[:2]
    return [(image[:h//2, :w//2], (0, 0)),
            (image[:h//2, w//2:], (w//2, 0)),
            (image[h//2:, :w//2], (0, h//2)),
            (image[h//2:, w//2:], (w//2, h//2))]


def statistics(vectors):
    if not len(vectors):
        return {key: None for key in ["average_displacement", "max_displacement",
                "min_displacement", "displacement_std", "median_dx", "median_dy"]}
    distances = np.linalg.norm(vectors, axis=1)
    return {"average_displacement": float(np.mean(distances)),
            "max_displacement": float(np.max(distances)),
            "min_displacement": float(np.min(distances)),
            "displacement_std": float(np.std(distances)),
            "median_dx": float(np.median(vectors[:, 0])),
            "median_dy": float(np.median(vectors[:, 1]))}


def analyze_pair(reference, target, matcher):
    if reference.shape != target.shape:
        raise ValueError("参考图像与目标图像的像素尺寸必须一致；请先统一裁剪范围与分辨率。")
    regions, vectors, points = [], [], []
    keypoint_counts = [0, 0]
    for (key, label), (image0, offset), (image1, _) in zip(
            REGIONS, quadrants(reference), quadrants(target)):
        raw = matcher.match(image0, image1)
        matched = consistent_matches(raw)
        keypoint_counts[0] += raw.keypoints_reference
        keypoint_counts[1] += raw.keypoints_target
        usable = len(matched.reference) >= 6
        delta = matched.target - matched.reference if usable else np.empty((0, 2))
        regions.append({"region": key, "label": label,
                        "status": "measured" if usable else "insufficient_matches",
                        "matches_count": len(matched.reference),
                        "raw_matches_count": len(raw.reference),
                        "keypoints1": raw.keypoints_reference, "keypoints2": raw.keypoints_target,
                        **statistics(delta)})
        if usable:
            vectors.extend(delta)
            points.extend(zip(matched.reference + offset, matched.target + offset))
    valid = sum(r["status"] == "measured" for r in regions)
    result = {"status": "completed" if valid == 4 else "partial" if valid else "unmeasurable",
              "engine": matcher.name, "unit": "px", "valid_regions": valid,
              "matches_count": len(vectors), "keypoints1": keypoint_counts[0],
              "keypoints2": keypoint_counts[1], "region_results": regions,
              **statistics(np.asarray(vectors).reshape(-1, 2))}
    result["notes"] = ["位移为图像像素坐标变化，包含相机运动与配准误差；未换算为物理形变。"]
    if valid < 4:
        result["notes"].append("部分区域无法测量；缺失值保留为空，不作为零位移。")
    return result, points


def matching_preview(reference, target, points):
    # Scale only the visualization, never the measurement coordinates.
    h, w = reference.shape
    canvas = np.concatenate([cv2.cvtColor(reference, cv2.COLOR_GRAY2BGR),
                             cv2.cvtColor(target, cv2.COLOR_GRAY2BGR)], axis=1)
    for p0, p1 in points[::max(1, len(points)//100)]:
        a = tuple(np.rint(p0).astype(int))
        b = tuple(np.rint(p1 + (w, 0)).astype(int))
        cv2.line(canvas, a, b, (130, 190, 38), 1, cv2.LINE_AA)
        cv2.circle(canvas, a, 2, (20, 110, 240), -1)
    if canvas.shape[1] > 1600:
        canvas = cv2.resize(canvas, (1600, round(h * 1600 / (w * 2))))
    ok, png = cv2.imencode(".png", canvas)
    if not ok:
        raise RuntimeError("无法生成匹配图")
    return png.tobytes()


def temporal_trends(comparisons, threshold=.5):
    """Regress against elapsed calendar days, excluding missing measurements."""
    first = date.fromisoformat(comparisons[0]["date"])
    output = []
    for key, label in REGIONS:
        pairs = []
        series = []
        for sample in comparisons:
            region = next(r for r in sample["region_results"] if r["region"] == key)
            value = region["average_displacement"]
            series.append(value)
            if value is not None:
                pairs.append(((date.fromisoformat(sample["date"]) - first).days, value))
        slope = None
        trend = "insufficient_data"
        if len(pairs) >= 3:
            x, y = np.array(pairs).T
            slope = float(np.polyfit(x, y, 1)[0])
            trend = "increasing" if slope > threshold else "decreasing" if slope < -threshold else "no_clear_trend"
        output.append({"region": key, "label": label, "series": series,
                       "valid_samples": len(pairs), "missing_samples": len(series) - len(pairs),
                       "slope_px_per_day": slope, "trend": trend})
    return {"regions": output, "threshold_px_per_day": threshold,
            "has_increasing_trend": any(r["trend"] == "increasing" for r in output),
            "notes": ["趋势只反映像素位移幅值随日期的变化，不构成房屋安全鉴定。",
                      "每个区域至少需要三个有效对比日期；缺失点不参与回归。"]}
