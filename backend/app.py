"""One FastAPI entry point for the API and the original web interface."""
import csv
from datetime import date, datetime, timezone
from io import BytesIO, StringIO
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import Literal
from uuid import uuid4

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import numpy as np
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from .analysis import analyze_pair, matching_preview, temporal_trends
from .config import ROOT, Settings
from .matching import EngineUnavailable, SiftMatcher
from .superglue_adapter import SuperGlueMatcher

log = logging.getLogger(__name__)
Engine = Literal["superglue", "sift"]
VERSION = "0.1.0-preview"


def create_app(settings=None):
    settings = settings or Settings.from_env()
    application = FastAPI(title="无靶标自建房变形监测系统", version=VERSION)
    application.state.settings = settings
    engines = {"sift": SiftMatcher(), "superglue": SuperGlueMatcher(settings)}
    busy = threading.Lock()

    async def decode(upload):
        try:
            content = bytearray()
            while chunk := await upload.read(1024 * 1024):
                content.extend(chunk)
                if len(content) > settings.max_upload_bytes:
                    raise HTTPException(413, "单张图片不得超过 12 MiB。")
            try:
                with Image.open(BytesIO(content)) as image:
                    if image.format not in {"JPEG", "PNG", "BMP", "TIFF"}:
                        raise ValueError("仅支持 JPEG、PNG、BMP 和 TIFF 图像。")
                    w, h = image.size
                    if min(w, h) < 64 or w * h > settings.max_pixels:
                        raise ValueError("图片边长至少 64 像素，且总像素不得超过 1200 万。")
                    if getattr(image, "n_frames", 1) != 1:
                        raise ValueError("请使用单帧图片。")
                    image.verify()
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                raise ValueError("图片无法解码，或文件内容不是有效图像。") from exc
            # Ignore EXIF orientation consistently: reported coordinates refer to the encoded raster.
            decoded = cv2.imdecode(np.frombuffer(content, np.uint8),
                                   cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)
            if decoded is None:
                raise ValueError("OpenCV 无法读取该图片。")
            return decoded
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        finally:
            await upload.close()

    def save_report(result):
        directory = settings.data_dir / result["task_id"]
        directory.mkdir(parents=True, exist_ok=True)
        pending = directory / "report.json.tmp"
        pending.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), "utf-8")
        pending.replace(directory / "report.json")

    def execute(engine, operation):
        if not busy.acquire(blocking=False):
            raise HTTPException(429, "当前有分析任务正在运行，请稍后重试。")
        try:
            return operation(engines[engine])
        except EngineUnavailable as exc:
            if exc.__cause__ is not None:
                log.exception("Research engine failed")
            else:
                log.info("Research engine unavailable: %s", exc)
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        finally:
            busy.release()

    def pair_job(image0, image1, matcher, task_id):
        result, points = analyze_pair(image0, image1, matcher)
        if result["valid_regions"]:
            directory = settings.data_dir / task_id
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "matches.png").write_bytes(matching_preview(image0, image1, points))
            result["match_image_path"] = f"/api/tasks/{task_id}/matches.png"
        return result

    @application.get("/api/health")
    def health():
        research = engines["superglue"]
        error = research.configuration_error()
        return {"status": "ok", "version": VERSION, "busy": busy.locked(),
                "engines": {"sift": {"available": True, "device": "CPU", "label": "SIFT / CPU 基线"},
                            "superglue": {"available": error is None,
                                          "loaded": research.loaded,
                                          "device": research.device,
                                          "message": error or "已配置，将在首次分析时加载并验证。"}}}

    @application.post("/api/analyze/upload")
    async def pair(image1: UploadFile = File(...), image2: UploadFile = File(...),
                   engine: Engine = Form("superglue")):
        image0, image1_array = await decode(image1), await decode(image2)

        def job(matcher):
            start = time.perf_counter()
            task_id = uuid4().hex
            result = pair_job(image0, image1_array, matcher, task_id)
            result.update(task_id=task_id, mode="pair", processing_time=time.perf_counter() - start,
                          timestamp=datetime.now(timezone.utc).isoformat(),
                          report_url=f"/api/tasks/{task_id}/report.json")
            save_report(result)
            return result

        return await run_in_threadpool(execute, engine, job)

    @application.post("/api/analyze/multi-region")
    async def sequence(base_image: UploadFile = File(...),
                       comparison_images: list[UploadFile] = File(...),
                       dates: str = Form(...), base_date: date = Form(...),
                       engine: Engine = Form("superglue"),
                       slope_threshold: float = Form(.5, gt=0, le=1000)):
        if not 1 <= len(comparison_images) <= settings.max_comparisons:
            raise HTTPException(400, "需要 1 至 20 张对比图像。")
        try:
            supplied = json.loads(dates)
            if not isinstance(supplied, list) or len(supplied) != len(comparison_images):
                raise ValueError("日期数量必须与对比图像数量一致。")
            if any(not isinstance(d, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in supplied):
                raise ValueError("日期格式必须为 YYYY-MM-DD。")
            parsed = [date.fromisoformat(d) for d in supplied]
            if len(set(parsed)) != len(parsed):
                raise ValueError("对比图像的拍摄日期不能重复。")
            if any(d <= base_date for d in parsed):
                raise ValueError("对比日期必须晚于基础图像的拍摄日期。")
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, f"日期输入无效：{exc}") from exc
        reference = await decode(base_image)
        images = []
        for capture_date, upload in zip(parsed, comparison_images):
            target = await decode(upload)
            if target.shape != reference.shape:
                raise HTTPException(400, "所有图像必须与基础图像具有相同像素尺寸。")
            images.append((capture_date.isoformat(), target))
        images.sort(key=lambda row: row[0])

        def job(matcher):
            start = time.perf_counter()
            comparisons = []
            for capture_date, target in images:
                result, _ = analyze_pair(reference, target, matcher)
                comparisons.append({"date": capture_date, **result})
            measured = sum(r["valid_regions"] for r in comparisons)
            result = {"task_id": uuid4().hex, "mode": "sequence", "unit": "px", "engine": engine,
                      "base_date": base_date.isoformat(),
                      "status": "completed" if measured == len(images) * 4 else "partial" if measured else "unmeasurable",
                      "comparison_results": comparisons,
                      "trend_analysis": temporal_trends(comparisons, slope_threshold),
                      "processing_time": time.perf_counter() - start,
                      "timestamp": datetime.now(timezone.utc).isoformat()}
            result["report_url"] = f"/api/tasks/{result['task_id']}/report.json"
            save_report(result)
            return result

        return await run_in_threadpool(execute, engine, job)

    def task_directory(task_id):
        if not re.fullmatch(r"[0-9a-f]{32}", task_id):
            raise HTTPException(404, "任务不存在。")
        directory = settings.data_dir / task_id
        if not (directory / "report.json").is_file():
            raise HTTPException(404, "任务不存在。")
        return directory

    @application.get("/api/tasks/{task_id}/{artifact}")
    def artifact(task_id: str, artifact: Literal["matches.png", "report.json", "report.csv"]):
        directory = task_directory(task_id)
        if artifact == "report.csv":
            report = json.loads((directory / "report.json").read_text("utf-8"))
            rows = report.get("comparison_results", [report])
            text = StringIO(newline="")
            keys = ["date", "region", "status", "matches_count", "average_displacement",
                    "median_dx", "median_dy"]
            writer = csv.DictWriter(text, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                for region in row["region_results"]:
                    writer.writerow({**region, "date": row.get("date", "")})
            return Response(text.getvalue().encode("utf-8-sig"), media_type="text/csv",
                            headers={"Content-Disposition": f'attachment; filename="{task_id}.csv"'})
        path = directory / artifact
        if not path.is_file():
            raise HTTPException(404, "该任务没有此文件。")
        return FileResponse(path, media_type="application/json" if artifact.endswith("json") else "image/png",
                            filename=f"{task_id}.json" if artifact.endswith("json") else None)

    @application.get("/api/history")
    def history():
        reports = sorted(settings.data_dir.glob("*/report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        entries = []
        for path in reports[:20]:
            try:
                report = json.loads(path.read_text("utf-8"))
                entries.append({k: report[k] for k in ["task_id", "mode", "status", "engine", "timestamp", "report_url"]})
            except (OSError, ValueError, KeyError):
                log.warning("Skipped unreadable report")
        return {"items": entries}

    @application.get("/")
    def index():
        return FileResponse(ROOT / "frontend/app.html")

    for name in ["css", "js"]:
        application.mount(f"/{name}", StaticFiles(directory=ROOT / "frontend" / name), name=name)
    application.mount("/examples", StaticFiles(directory=ROOT / "examples"), name="examples")
    return application


app = create_app()
