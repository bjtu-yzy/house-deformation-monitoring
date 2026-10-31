"""Generate reproducible synthetic images, NOT a building-monitoring benchmark."""
from pathlib import Path
import cv2
import numpy as np


def generate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261031)
    image = np.full((640, 960, 3), (223, 233, 241), dtype=np.uint8)
    cv2.rectangle(image, (55, 40), (900, 610), (150, 170, 185), -1)
    for y in range(60, 600, 40):
        for x in range(65 + (20 if y % 80 else 0), 900, 60):
            shade = int(rng.integers(105, 210))
            cv2.rectangle(image, (x, y), (x + 54, y + 33), (shade, shade + 10, min(255, shade + 20)), -1)
    for y in [110, 310, 500]:
        for x in [150, 370, 590, 780]:
            cv2.rectangle(image, (x, y), (x + 72, y + 78), (48, 69, 87), -1)
            cv2.line(image, (x + 36, y), (x + 36, y + 78), (220, 230, 240), 3)
            cv2.line(image, (x, y + 39), (x + 72, y + 39), (220, 230, 240), 3)
    noise = rng.normal(0, 5, image.shape)
    image = np.clip(image.astype(float) + noise, 0, 255).astype(np.uint8)
    cv2.imwrite(str(directory / "reference.png"), image)
    for index, (dx, dy) in enumerate([(4, 3), (8, 6), (12, 9)], 1):
        shifted = cv2.warpAffine(image, np.float32([[1, 0, dx], [0, 1, dy]]), (960, 640), borderMode=cv2.BORDER_REFLECT)
        cv2.imwrite(str(directory / f"target-{index}.png"), shifted)
    return image


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "examples")
