"""Feature-matcher interface and a CPU baseline with real image measurements."""
from dataclasses import dataclass
import cv2
import numpy as np


class EngineUnavailable(RuntimeError):
    pass


@dataclass
class Matches:
    reference: np.ndarray
    target: np.ndarray
    keypoints_reference: int
    keypoints_target: int


class SiftMatcher:
    name = "sift"
    device = "CPU"

    def match(self, reference, target):
        detector = cv2.SIFT_create(nfeatures=2048)
        points0, descriptors0 = detector.detectAndCompute(reference, None)
        points1, descriptors1 = detector.detectAndCompute(target, None)
        empty = np.empty((0, 2), dtype=np.float32)
        if descriptors0 is None or descriptors1 is None:
            return Matches(empty, empty, len(points0), len(points1))
        matcher = cv2.BFMatcher(cv2.NORM_L2)
        forward = matcher.knnMatch(descriptors0, descriptors1, k=2)
        reverse = matcher.knnMatch(descriptors1, descriptors0, k=2)
        backwards = {
            row[0].queryIdx: row[0].trainIdx for row in reverse
            if len(row) == 2 and row[0].distance < .75 * row[1].distance
        }
        good = [row[0] for row in forward if len(row) == 2
                and row[0].distance < .75 * row[1].distance
                and backwards.get(row[0].trainIdx) == row[0].queryIdx]
        return Matches(
            np.array([points0[m.queryIdx].pt for m in good], dtype=np.float32).reshape(-1, 2),
            np.array([points1[m.trainIdx].pt for m in good], dtype=np.float32).reshape(-1, 2),
            len(points0), len(points1),
        )


def consistent_matches(matches):
    """Reject gross vector outliers, keeping displacement in original-image pixels."""
    if len(matches.reference) < 6:
        return matches
    vectors = matches.target - matches.reference
    residual = np.linalg.norm(vectors - np.median(vectors, axis=0), axis=1)
    median = np.median(residual)
    mad = np.median(np.abs(residual - median))
    keep = residual <= max(2., median + 3 * 1.4826 * mad)
    return Matches(matches.reference[keep], matches.target[keep],
                   matches.keypoints_reference, matches.keypoints_target)
