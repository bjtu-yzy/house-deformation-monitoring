"""Adapter for the user's external research fork; no vendor model source is bundled.

The legacy fork expects N×256 descriptors and computes a training loss even in
eval mode. A single dummy loss index is supplied only for that unused code path;
it is not a supervision label, measurement, or evaluation metric.
"""
import importlib.util
from pathlib import Path
import threading
import numpy as np
from .matching import EngineUnavailable, Matches


class SuperGlueMatcher:
    name = "superglue"

    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.Lock()
        self.loaded = False
        self.device = "未加载"

    def configuration_error(self):
        root = self.settings.legacy_dir
        if root is None:
            return "未配置外部研究模型目录；请设置 HM_SUPERGLUE_DIR，或选择 SIFT 基线。"
        for filename in ["models/superpoint.py", "models/superglue.py",
                         "models/weights/superpoint_v1.pth"]:
            if not (root / filename).is_file():
                return f"外部研究目录缺少 {filename}。"
        checkpoint = self.settings.checkpoint or root / "model_best_superglue.pth"
        if not checkpoint.is_file():
            return "未找到研究权重；请设置 HM_SUPERGLUE_WEIGHTS。"
        if importlib.util.find_spec("torch") is None:
            return "未安装可选 PyTorch 依赖；请阅读 docs/models.md。"
        return None

    @staticmethod
    def _module(path: Path, name: str):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        # Read-only loading also avoids creating __pycache__ in the original project.
        code = compile(path.read_text("utf-8-sig"), str(path), "exec")
        exec(code, module.__dict__)
        return module

    def _load(self):
        if self.loaded:
            return
        error = self.configuration_error()
        if error:
            raise EngineUnavailable(error)
        import torch
        if tuple(int(n) for n in torch.__version__.split("+")[0].split(".")[:2]) < (2, 6):
            raise EngineUnavailable("研究适配器要求 PyTorch 2.6 或以上。")
        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        root = self.settings.legacy_dir
        sp = self._module(root / "models/superpoint.py", "hm_external_superpoint")
        sg = self._module(root / "models/superglue.py", "hm_external_superglue")
        # The external SuperPoint constructor loads its local default weights.
        self.superpoint = sp.SuperPoint({"nms_radius": 4, "keypoint_threshold": .005,
                                        "max_keypoints": 1024}).eval().to(self.device)
        self.superglue = sg.SuperGlue({"sinkhorn_iterations": 20,
                                      "match_threshold": .2}).double()
        weights = self.settings.checkpoint or root / "model_best_superglue.pth"
        state = torch.load(weights, map_location="cpu", weights_only=True)
        self.superglue.load_state_dict(state, strict=True)
        self.superglue = self.superglue.eval().to(self.device)
        self.loaded = True

    def match(self, reference, target):
        with self.lock:
            try:
                self._load()
                return self._infer(reference, target)
            except EngineUnavailable:
                raise
            except Exception as exc:
                raise EngineUnavailable("研究模型加载或推理失败；请检查外部源码、权重与 PyTorch 的兼容性。") from exc

    def _infer(self, reference, target):
        torch = self.torch
        images = [torch.from_numpy(image.astype(np.float32) / 255.)[None, None].to(self.device)
                  for image in [reference, target]]
        with torch.inference_mode():
            features = [self.superpoint({"image": image}) for image in images]
            counts = [len(f["keypoints"][0]) for f in features]
            if min(counts) == 0:
                empty = np.empty((0, 2), dtype=np.float32)
                return Matches(empty, empty, *counts)
            data = {"file_name": "inference", "image0": images[0].double(),
                    "image1": images[1].double(),
                    "all_matches": torch.zeros((2, 1, 1), dtype=torch.long, device=self.device)}
            for i, f in enumerate(features):
                data[f"keypoints{i}"] = f["keypoints"][0][None].double()
                data[f"descriptors{i}"] = (f["descriptors"][0].T / 256.).double()
                data[f"scores{i}"] = f["scores"][0][:, None].double()
            output = self.superglue(data)
            indices = output["matches0"].reshape(-1).cpu().numpy()
            valid = (indices >= 0) & (indices < counts[1])
            k0, k1 = [f["keypoints"][0].cpu().numpy() for f in features]
            return Matches(k0[valid], k1[indices[valid]], *counts)
