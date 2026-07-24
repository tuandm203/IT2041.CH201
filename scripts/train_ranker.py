#!/usr/bin/env python3
"""Train the GP2 course-priority ranker from official UIT curricula."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.course_features import FEATURE_COLUMNS, build_feature_row  # noqa: E402


COHORTS = ("K2012", "K2013", "K2014", "K2015")
PROGRAMS_DIR = REPO_ROOT / "data" / "programs"
MODEL_DIR = REPO_ROOT / "data" / "models"
MODEL_PATH = MODEL_DIR / "course_priority_ranker.joblib"
FEATURE_COLUMNS_PATH = MODEL_DIR / "feature_columns.json"


def load_training_data() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    rows: list[dict[str, float]] = []
    labels: list[float] = []
    groups: list[str] = []

    for cohort in COHORTS:
        for program_path in sorted((PROGRAMS_DIR / cohort).glob("*/standard.json")):
            with program_path.open(encoding="utf-8") as program_file:
                program = json.load(program_file)

            major = str(program.get("major") or program_path.parent.name)
            for course in program.get("courses", []):
                semester = course.get("semester")
                course_id = course.get("course_id")
                if semester is None or not course_id:
                    continue
                rows.append(build_feature_row(str(course_id), major, program))
                labels.append(float(semester))
                groups.append(major)

    frame = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    return frame, np.asarray(labels), np.asarray(groups)


def evaluate_model(
    name: str,
    estimator: object,
    features: pd.DataFrame,
    labels: np.ndarray,
    groups: np.ndarray,
) -> tuple[float, float]:
    splitter = GroupKFold(n_splits=len(np.unique(groups)))
    fold_mae: list[float] = []
    fold_r2: list[float] = []

    print(f"\n{name} GroupKFold results:")
    for fold, (train_indices, test_indices) in enumerate(
        splitter.split(features, labels, groups),
        start=1,
    ):
        fold_model = clone(estimator)
        fold_model.fit(features.iloc[train_indices], labels[train_indices])
        predictions = fold_model.predict(features.iloc[test_indices])
        mae = mean_absolute_error(labels[test_indices], predictions)
        r2 = r2_score(labels[test_indices], predictions)
        held_out = ", ".join(sorted(set(groups[test_indices])))
        fold_mae.append(float(mae))
        fold_r2.append(float(r2))
        print(
            f"  Fold {fold} (held-out major: {held_out}): "
            f"MAE={mae:.4f}, R2={r2:.4f}"
        )

    mean_mae = float(np.mean(fold_mae))
    mean_r2 = float(np.mean(fold_r2))
    print(
        f"  Mean: MAE={mean_mae:.4f} (+/- {np.std(fold_mae):.4f}), "
        f"R2={mean_r2:.4f} (+/- {np.std(fold_r2):.4f})"
    )
    return mean_mae, mean_r2


def main() -> None:
    features, labels, groups = load_training_data()
    print(
        f"Loaded {len(features)} real curriculum labels from "
        f"{len(COHORTS)} cohorts and {len(np.unique(groups))} majors."
    )
    print(f"Feature columns: {FEATURE_COLUMNS}")

    ridge = Ridge(alpha=1.0)
    evaluate_model("Ridge (GP2 primary)", ridge, features, labels, groups)
    evaluate_model(
        "GradientBoostingRegressor (ablation)",
        GradientBoostingRegressor(random_state=42),
        features,
        labels,
        groups,
    )

    ridge.fit(features, labels)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(ridge, MODEL_PATH)
    with FEATURE_COLUMNS_PATH.open("w", encoding="utf-8") as columns_file:
        json.dump(FEATURE_COLUMNS, columns_file, ensure_ascii=False, indent=2)
        columns_file.write("\n")

    coefficients = ", ".join(
        f"{name}={coefficient:.6f}"
        for name, coefficient in zip(FEATURE_COLUMNS, ridge.coef_)
    )
    print(f"\nRidge coefficients: {coefficients}")
    print(f"Ridge intercept: {ridge.intercept_:.6f}")
    print(f"Saved model: {MODEL_PATH}")
    print(f"Saved feature order: {FEATURE_COLUMNS_PATH}")


if __name__ == "__main__":
    main()
