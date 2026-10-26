"""Traffic sign classifier: HOG + colour histogram, PCA, linear SVM.

Trained on the German Traffic Sign Recognition Benchmark (GTSRB, 43 classes)
plus one extra "background" class made of random crops from road videos, so
that candidate regions which are not signs can be rejected. HOG with a linear
SVM is cheap enough for a Raspberry Pi, which was the target platform.
"""
from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

SIZE = 40
BACKGROUND = 43

NAMES = [
    "speed limit 20", "speed limit 30", "speed limit 50", "speed limit 60",
    "speed limit 70", "speed limit 80", "end of speed limit 80", "speed limit 100",
    "speed limit 120", "no overtaking", "no overtaking for trucks", "priority at next junction",
    "priority road", "yield", "stop", "no vehicles", "no trucks", "no entry",
    "danger", "bend left", "bend right", "double bend", "bumpy road", "slippery road",
    "road narrows right", "road works", "traffic signals", "pedestrians", "children",
    "bicycles", "ice or snow", "wild animals", "end of all limits", "turn right ahead",
    "turn left ahead", "ahead only", "ahead or right", "ahead or left", "keep right",
    "keep left", "roundabout", "end of no overtaking", "end of no overtaking for trucks",
    "background",
]
SPEED = {0: 20, 1: 30, 2: 50, 3: 60, 4: 70, 5: 80, 7: 100, 8: 120}

_HOG = cv2.HOGDescriptor((SIZE, SIZE), (10, 10), (5, 5), (5, 5), 9)
_CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))


def features(crop: np.ndarray) -> np.ndarray:
    """HOG of the contrast normalised grey image plus a coarse hue/saturation
    histogram (red, blue and white signs look alike in grey)."""
    img = cv2.resize(crop, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    grey = _CLAHE.apply(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    hog = _HOG.compute(grey).ravel()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [12, 3], [0, 180, 0, 256]).ravel()
    hist /= hist.sum() + 1e-6
    return np.concatenate([hog, 2.0 * hist]).astype(np.float32)


def feature_matrix(crops: Iterable[np.ndarray]) -> np.ndarray:
    return np.stack([features(c) for c in crops])


# --- data ------------------------------------------------------------------

def _crop_roi(image, row):
    x1, y1, x2, y2 = (int(row[k]) for k in ("Roi.X1", "Roi.Y1", "Roi.X2", "Roi.Y2"))
    # keep a margin like the detector does
    h, w = image.shape[:2]
    mx, my = int(0.1 * (x2 - x1)), int(0.1 * (y2 - y1))
    return image[max(0, y1 - my):min(h, y2 + my), max(0, x1 - mx):min(w, x2 + mx)]


def load_gtsrb(root, split: str, limit: Optional[int] = None, seed: int = 0):
    """Crops and labels from the GTSRB csv files (Train.csv or Test.csv)."""
    root = Path(root)
    with (root / ("%s.csv" % split.capitalize())).open(newline="") as f:
        rows = list(csv.DictReader(f))
    if limit and limit < len(rows):
        rng = np.random.default_rng(seed)
        rows = [rows[i] for i in rng.choice(len(rows), limit, replace=False)]
    crops, labels = [], []
    for row in rows:
        image = cv2.imread(str(root / row["Path"]))
        if image is None:
            continue
        crops.append(_crop_roi(image, row))
        labels.append(int(row["ClassId"]))
    return crops, np.array(labels)


def background_crops(videos: Sequence, n: int, seed: int = 0, sizes=(16, 90)):
    """Random square crops from road videos as the 'no sign' class."""
    rng = np.random.default_rng(seed)
    crops = []
    per_video = int(np.ceil(n / max(1, len(videos))))
    for path in videos:
        cap = cv2.VideoCapture(str(path))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for idx in sorted(rng.choice(max(1, count), min(count, per_video // 4 + 1), replace=False)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if not ok:
                continue
            if frame.shape[1] > 960:
                frame = cv2.resize(frame, (960, int(frame.shape[0] * 960 / frame.shape[1])))
            H, W = frame.shape[:2]
            for _ in range(4):
                s = int(rng.integers(*sizes))
                x = int(rng.integers(0, W - s))
                y = int(rng.integers(0, int(H * 0.75) - s))
                crops.append(frame[y:y + s, x:x + s])
        cap.release()
    return crops[:n]


# --- model -----------------------------------------------------------------

@dataclass
class SignClassifier:
    model: object
    meta: dict

    def predict(self, crops: Sequence[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """Class ids and decision margins (best minus second best score)."""
        if not len(crops):
            return np.zeros(0, int), np.zeros(0)
        X = feature_matrix(crops)
        scores = self.model.decision_function(X)
        order = np.argsort(scores, axis=1)
        best = order[:, -1]
        margin = scores[np.arange(len(X)), best] - scores[np.arange(len(X)), order[:, -2]]
        classes = np.asarray(self.model.classes_)[best]
        return classes, margin

    def save(self, path):
        import joblib
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path)
        path.with_suffix(".json").write_text(json.dumps(self.meta, indent=1))

    @classmethod
    def load(cls, path):
        import joblib
        path = Path(path)
        meta = {}
        if path.with_suffix(".json").is_file():
            meta = json.loads(path.with_suffix(".json").read_text())
        return cls(joblib.load(path), meta)


def training_set(gtsrb_root, background_videos, n_background=6000, limit=None,
                 cache: Optional[Path] = None, log=print):
    """Feature matrix and labels, cached as .npz because extracting 45 000
    feature vectors takes a few minutes."""
    if cache is not None and Path(cache).is_file():
        z = np.load(cache)
        return z["X"], z["y"], int(z["n_gtsrb"]), int(z["n_background"])
    t0 = time.perf_counter()
    crops, labels = load_gtsrb(gtsrb_root, "train", limit)
    bg = background_crops(background_videos, n_background)
    log("training crops: %d GTSRB + %d background (%.0fs)" % (len(crops), len(bg), time.perf_counter() - t0))
    X = feature_matrix(list(crops) + bg)
    y = np.concatenate([labels, np.full(len(bg), BACKGROUND)])
    if cache is not None:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, X=X, y=y, n_gtsrb=len(crops), n_background=len(bg))
    return X, y, len(crops), len(bg)


def train(gtsrb_root, background_videos, n_background=6000, C=0.05, limit=None,
          cache: Optional[Path] = None, n_components: int = 400, log=print) -> SignClassifier:
    from sklearn.decomposition import PCA
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import LinearSVC

    t0 = time.perf_counter()
    X, y, n_gtsrb, n_bg = training_set(gtsrb_root, background_videos, n_background, limit, cache, log)
    # PCA to 400 dimensions keeps the accuracy of the full 1800 features
    # (93.9 % vs 93.5 % on the GTSRB test set) and cuts training from almost
    # an hour to about two minutes; primal solver since samples >> features
    model = make_pipeline(StandardScaler(), PCA(n_components, random_state=0),
                          LinearSVC(C=C, dual=False, max_iter=2000))
    model.fit(X, y)
    log("trained in %.0fs, %d features" % (time.perf_counter() - t0, X.shape[1]))
    meta = {"features": int(X.shape[1]), "pca": n_components, "size": SIZE, "C": C,
            "train_gtsrb": int(n_gtsrb), "train_background": int(n_bg),
            "background_videos": [Path(v).name for v in background_videos]}
    return SignClassifier(model, meta)


def evaluate(clf: SignClassifier, gtsrb_root, limit=None) -> dict:
    crops, labels = load_gtsrb(gtsrb_root, "test", limit)
    t0 = time.perf_counter()
    pred, margin = clf.predict(crops)
    per_crop_ms = 1000 * (time.perf_counter() - t0) / max(1, len(crops))
    speed = np.isin(labels, list(SPEED))
    conf = np.zeros((44, 44), dtype=int)
    np.add.at(conf, (labels, pred), 1)
    per_class = {NAMES[c]: float(conf[c, c] / conf[c].sum()) for c in range(43) if conf[c].sum()}
    return {
        "test_images": int(len(labels)),
        "accuracy": float(np.mean(pred == labels)),
        "speed_limit_accuracy": float(np.mean(pred[speed] == labels[speed])),
        "rejected_as_background": float(np.mean(pred == BACKGROUND)),
        "ms_per_crop": round(per_crop_ms, 3),
        "per_class_accuracy": per_class,
        "confusion": conf.tolist(),
    }
