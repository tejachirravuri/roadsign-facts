from pathlib import Path

import numpy as np
import pytest

from roadsign.classifier import BACKGROUND, NAMES, SPEED, LinearModel, SignClassifier, features

MODEL = Path(__file__).resolve().parent.parent / "models" / "signs_hog_svm.npz"


def test_shipped_model_loads_and_scores():
    clf = SignClassifier.load(MODEL)
    assert len(clf.model.classes_) == 44
    assert clf.meta["test_accuracy"] > 0.9
    crops = [np.full((40, 40, 3), 128, np.uint8), np.zeros((25, 31, 3), np.uint8)]
    classes, margins = clf.predict(crops)
    assert classes.shape == margins.shape == (2,)
    assert all(0 <= c <= BACKGROUND for c in classes)
    assert (margins >= 0).all()


def test_features_shape_and_names():
    f = features(np.zeros((33, 47, 3), np.uint8))
    assert f.shape == (1800,)
    assert len(NAMES) == 44 and NAMES[BACKGROUND] == "background"
    assert SPEED[2] == 50


def test_numpy_model_matches_sklearn(tmp_path):
    sklearn = pytest.importorskip("sklearn")
    from sklearn.decomposition import PCA
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import LinearSVC
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 20))
    y = (X[:, 0] > 0).astype(int) + (X[:, 1] > 0)
    pipe = make_pipeline(StandardScaler(), PCA(8), LinearSVC(dual=False)).fit(X, y)
    clf = SignClassifier(LinearModel.from_sklearn(pipe), {})
    clf.save(tmp_path / "m.npz")
    back = SignClassifier.load(tmp_path / "m.npz")
    assert np.allclose(back.model.decision_function(X), pipe.decision_function(X), atol=1e-4)
