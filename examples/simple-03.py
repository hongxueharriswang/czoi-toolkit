"""
anomaly.py — Unsupervised anomaly detection on access logs.

Demonstrates the paper's §5.1 neural component for anomaly detection:
  * Generate synthetic normal access patterns and anomalous outliers.
  * Normalise features to comparable scales (raw IDs and hours are not).
  * Train the CZOI AnomalyDetector (an autoencoder) on normal data only.
  * Score new samples and classify them via the learned threshold.
  * Measure precision / recall / F1 against the synthetic ground truth.
  * Show how real CZOI access-log records map into the feature vector.
"""
from __future__ import annotations

import numpy as np

from czoi import AnomalyDetector

SEED = 42
np.random.seed(SEED)

# ---- World constants -------------------------------------------------
N_NORMAL   = 1000
N_ANOMALY  = 50
N_FEATURES = 5          # user, zone, operation, hour_of_day, day_of_week

# Feature bounds (used for z-score normalisation).
BOUNDS = {
    "user_id":      (0, 9),
    "zone_id":      (0, 4),
    "operation_id": (0, 9),
    "hour":         (0, 23),
    "day_of_week":  (0, 6),
}


# =====================================================================
# 1. Generate synthetic access logs
# =====================================================================
def _normalise(raw: np.ndarray) -> np.ndarray:
    """Z-score normalise each column so the autoencoder sees
    comparable scales across categorical IDs and hours."""
    mean = raw.mean(axis=0)
    std  = raw.std(axis=0)
    std[std == 0] = 1.0
    return (raw - mean) / std


def generate_normal_logs(n: int) -> np.ndarray:
    """Normal session: work-hour traffic, common user/zone/op IDs.

    Features per row:
      [user_id, zone_id, operation_id, hour, day_of_week]
    """
    user_id  = np.random.randint(0, 10, n)
    zone_id  = np.random.randint(0, 5, n)
    op_id    = np.random.randint(0, 10, n)
    # Bimodal work-hour distribution (morning + afternoon).
    hour = np.where(
        np.random.random(n) < 0.5,
        np.random.normal(10, 1.5, n),
        np.random.normal(15, 1.5, n),
    )
    hour = np.clip(hour, 0, 23)
    # Weekdays only (Mon–Fri).
    dow = np.random.randint(0, 5, n)
    return np.column_stack([user_id, zone_id, op_id, hour, dow])


def generate_anomalous_logs(n: int) -> np.ndarray:
    """Anomalous session: off-hours access, rare combinations, weekend.

    The features are deliberately drawn from wider distributions so
    they fall outside the training manifold. Ground truth is known.
    """
    user_id = np.random.randint(0, 10, n)
    # Rare zone for this user base — 4 out of 5 normal rows use zones 0–3.
    zone_id = np.random.choice([0, 1, 2, 3, 4], n, p=[0.05, 0.05, 0.05, 0.05, 0.80])
    op_id   = np.random.choice([0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                               n, p=[0.02]*9 + [0.82])
    # Off-hours: midnight to 5 am.
    hour    = np.random.uniform(0, 5, n)
    # Weekend.
    dow     = np.random.randint(5, 7, n)
    return np.column_stack([user_id, zone_id, op_id, hour, dow])


# =====================================================================
# 2. Train and evaluate
# =====================================================================
def main() -> None:
    print("=" * 68)
    print("Anomaly detector — training and evaluation")
    print("=" * 68)

    # ---- Data ------------------------------------------------------
    normal_raw = generate_normal_logs(N_NORMAL)
    anomaly_raw = generate_anomalous_logs(N_ANOMALY)

    # Hold out some normal data for threshold calibration and testing.
    n_train = int(N_NORMAL * 0.8)
    train_raw, held_out_normal_raw = normal_raw[:n_train], normal_raw[n_train:]

    # Normalise: fit statistics on training data only.
    mean = train_raw.mean(axis=0)
    std  = train_raw.std(axis=0)
    std[std == 0] = 1.0

    def norm(x: np.ndarray) -> np.ndarray:
        return (x - mean) / std

    train_X           = norm(train_raw)
    held_out_normal_X = norm(held_out_normal_raw)
    anomaly_X         = norm(anomaly_raw)

    # ---- Build and train the detector ------------------------------
    detector = AnomalyDetector(
        name="access_log_anomaly",
        input_dim=N_FEATURES,
        latent_dim=3,
        threshold=0.5,      # placeholder, recalibrated in `fit`
        seed=SEED,
    )
    detector.fit(train_X, epochs=300, lr=0.05)

    print(f"Training samples      : {len(train_X)}")
    print(f"Autoencoder latent dim: {detector.latent_dim}")
    print(f"Calibrated threshold  : {detector.threshold:.4f}")
    print()

    # ---- Score samples ---------------------------------------------
    print("Normal held-out samples (expect low scores)")
    print("-" * 68)
    for i, x in enumerate(held_out_normal_X[:5]):
        s = detector.score(x)
        flag = "ANOMALY" if detector.is_anomalous(x) else "normal "
        print(f"  sample {i}: score={s:6.3f}  [{flag}]  "
              f"raw={held_out_normal_raw[i]}")

    print()
    print("Anomalous samples (expect higher scores)")
    print("-" * 68)
    for i, x in enumerate(anomaly_X[:5]):
        s = detector.score(x)
        flag = "ANOMALY" if detector.is_anomalous(x) else "normal "
        print(f"  sample {i}: score={s:6.3f}  [{flag}]  "
              f"raw={anomaly_raw[i]}")

    # ---- Evaluate against ground truth ----------------------------
    tp = fp = tn = fn = 0
    for x in held_out_normal_X:
        if detector.is_anomalous(x):
            fp += 1
        else:
            tn += 1
    for x in anomaly_X:
        if detector.is_anomalous(x):
            tp += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) else 0.0)

    print()
    print("=" * 68)
    print("Detection metrics")
    print("=" * 68)
    print(f"True positives  : {tp}")
    print(f"False positives : {fp}")
    print(f"True negatives  : {tn}")
    print(f"False negatives : {fn}")
    print(f"Precision       : {precision:.3f}")
    print(f"Recall          : {recall:.3f}")
    print(f"F1              : {f1:.3f}")

    # ---- Score distributions ---------------------------------------
    normal_scores  = np.array([detector.score(x) for x in held_out_normal_X])
    anomaly_scores = np.array([detector.score(x) for x in anomaly_X])
    print()
    print(f"Normal score  — mean: {normal_scores.mean():.3f}, "
          f"std: {normal_scores.std():.3f}")
    print(f"Anomaly score — mean: {anomaly_scores.mean():.3f}, "
          f"std: {anomaly_scores.std():.3f}")
    print(f"Separation    : "
          f"{anomaly_scores.mean() - normal_scores.mean():.3f}")


if __name__ == "__main__":
    main()