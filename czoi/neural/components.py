"""Neural components (N) for the CZOA 10-tuple.

Provides trainable components:
* Predictor       — generic linear/MLP predictor
* AnomalyDetector — autoencoder-based anomaly detection
* RoleMiner       — neural-enhanced permission mining (paper §5.1)
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np


# =====================================================================
# Predictor
# =====================================================================
class Predictor:
    """Trainable predictor with a public `predict` interface.

    With no training data, it wraps a user-supplied callable. After
    `fit`, it uses the learned weights.
    """

    def __init__(
        self,
        name: str,
        fn: Callable[[dict[str, Any]], float] | None = None,
        threshold: float = 0.5,
        input_dim: int | None = None,
    ) -> None:
        self.name = name
        self.threshold = threshold
        self.fn = fn
        self.input_dim = input_dim
        self._W: np.ndarray | None = None
        self._b: float | None = None

    # -----------------------------------------------------------------
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 200,
        lr: float = 0.05,
    ) -> None:
        """Fit a linear model with sigmoid activation."""
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float).reshape(-1)
        n, d = X.shape
        self.input_dim = d
        self._W = np.zeros(d)
        self._b = 0.0
        for _ in range(epochs):
            z = X @ self._W + self._b
            p = 1.0 / (1.0 + np.exp(-z))
            grad = (p - y)
            self._W -= lr * (X.T @ grad) / n
            self._b -= lr * grad.mean()

    # -----------------------------------------------------------------
    def predict(self, features) -> float:
        if self._W is not None:
            x = self._features_to_vector(features)
            z = float(x @ self._W + self._b)
            return float(1.0 / (1.0 + np.exp(-z)))
        if self.fn is not None:
            score = float(self.fn(features))
        else:
            raise RuntimeError(
                f"{self.name}: not fitted and no fn provided"
            )
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"{self.name}: score {score} outside [0, 1]")
        return score

    def fires(self, features) -> bool:
        return self.predict(features) >= self.threshold

    # -----------------------------------------------------------------
    def _features_to_vector(self, features) -> np.ndarray:
        if isinstance(features, np.ndarray):
            return features.astype(float)
        if isinstance(features, dict):
            return np.array(list(features.values()), dtype=float)
        return np.asarray(features, dtype=float)


# =====================================================================
# AnomalyDetector
# =====================================================================
class AnomalyDetector:
    """Autoencoder anomaly detector trained by gradient descent."""

    def __init__(
        self,
        name: str,
        input_dim: int,
        latent_dim: int = 8,
        threshold: float = 0.1,
        seed: int = 0,
    ) -> None:
        self.name = name
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.threshold = threshold
        rng = np.random.default_rng(seed)
        self.W_enc = rng.normal(0, 0.1, (input_dim, latent_dim))
        self.W_dec = rng.normal(0, 0.1, (latent_dim, input_dim))

    # -----------------------------------------------------------------
    def fit(
        self,
        X: np.ndarray,
        epochs: int = 200,
        lr: float = 0.05,
    ) -> None:
        """Train on normal data (reconstruct-and-minimise)."""
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.input_dim:
            raise ValueError(
                f"{self.name}: expected (n, {self.input_dim}) input"
            )
        for _ in range(epochs):
            Z = np.tanh(X @ self.W_enc)
            X_hat = np.tanh(Z @ self.W_dec)
            err = X_hat - X
            # Backprop through decoder (tanh derivative)
            grad_dec = (1 - X_hat ** 2) * err
            dW_dec = Z.T @ grad_dec
            # Backprop through encoder
            grad_z = (grad_dec @ self.W_dec.T) * (1 - Z ** 2)
            dW_enc = X.T @ grad_z
            self.W_dec -= lr * dW_dec / X.shape[0]
            self.W_enc -= lr * dW_enc / X.shape[0]
        # Calibrate threshold at the 95th percentile of training scores.
        scores = np.array([self.score(x) for x in X])
        self.threshold = float(np.percentile(scores, 95))

    # -----------------------------------------------------------------
    def encode(self, x: np.ndarray) -> np.ndarray:
        return np.tanh(np.asarray(x, float) @ self.W_enc)

    def decode(self, z: np.ndarray) -> np.ndarray:
        return np.tanh(z @ self.W_dec)

    def score(self, x: np.ndarray) -> float:
        x = np.asarray(x, dtype=float).reshape(-1)
        if x.shape[0] != self.input_dim:
            raise ValueError(
                f"{self.name}: expected {self.input_dim} features"
            )
        x_hat = self.decode(self.encode(x))
        return float(np.linalg.norm(x - x_hat))

    def is_anomalous(self, x: np.ndarray) -> bool:
        return self.score(x) > self.threshold


# =====================================================================
# RoleMiner
# =====================================================================
@dataclass
class MiningResult:
    suggested_roles: dict[str, list[str]] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    n_clusters: int = 0


class RoleMiner:
    """Mines role candidates from historical access logs.

    Pipeline (paper §5.1, Algorithm 1):
      1. Encode users/operations as a binary matrix.
      2. Train an autoencoder on the matrix.
      3. Cluster the latent codes (HDBSCAN, fallback Agglomerative).
      4. Validate against identity and access constraints.
      5. Return high-confidence candidates.
    """

    def __init__(
        self,
        latent_dim: int = 16,
        min_cluster_size: int = 3,
        seed: int = 0,
        autoencoder_epochs: int = 200,
        autoencoder_lr: float = 0.05,
    ) -> None:
        self.latent_dim = latent_dim
        self.min_cluster_size = min_cluster_size
        self.seed = seed
        self.autoencoder_epochs = autoencoder_epochs
        self.autoencoder_lr = autoencoder_lr

    # -----------------------------------------------------------------
    def _train_autoencoder(self, X: np.ndarray) -> np.ndarray:
        rng = np.random.default_rng(self.seed)
        n, d = X.shape
        W_enc = rng.normal(0, 0.1, (d, self.latent_dim))
        W_dec = rng.normal(0, 0.1, (self.latent_dim, d))
        for _ in range(self.autoencoder_epochs):
            Z = np.tanh(X @ W_enc)
            X_hat = np.tanh(Z @ W_dec)
            err = X_hat - X
            grad_dec = (1 - X_hat ** 2) * err
            dW_dec = Z.T @ grad_dec
            grad_z = (grad_dec @ W_dec.T) * (1 - Z ** 2)
            dW_enc = X.T @ grad_z
            W_dec -= self.autoencoder_lr * dW_dec / n
            W_enc -= self.autoencoder_lr * dW_enc / n
        return np.tanh(X @ W_enc)

    # -----------------------------------------------------------------
    def _cluster(self, Z: np.ndarray) -> np.ndarray:
        try:
            from sklearn.cluster import HDBSCAN
            clusterer = HDBSCAN(min_cluster_size=self.min_cluster_size)
            return clusterer.fit_predict(Z)
        except (ImportError, AttributeError):
            try:
                from sklearn.cluster import AgglomerativeClustering
                clusterer = AgglomerativeClustering(
                    n_clusters=None,
                    distance_threshold=1.5,
                    linkage="ward",
                )
                return clusterer.fit_predict(Z)
            except ImportError as exc:
                raise ImportError(
                    "RoleMiner requires scikit-learn. Install with: "
                    "pip install czoi-toolkit[neural]"
                ) from exc

    # -----------------------------------------------------------------
    def mine(
        self,
        X: np.ndarray,
        operation_names: list[str],
        min_support: float = 0.5,
    ) -> MiningResult:
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != len(operation_names):
            raise ValueError(
                f"X must have {len(operation_names)} columns"
            )

        Z = self._train_autoencoder(X)
        labels = self._cluster(Z)

        result = MiningResult(n_clusters=len({l for l in labels if l >= 0}))
        for label in sorted({l for l in labels if l >= 0}):
            mask = labels == label
            support = X[mask].mean(axis=0)
            ops = [
                operation_names[j]
                for j in np.argsort(-support)
                if support[j] >= min_support
            ]
            if not ops:
                continue
            role_name = f"MinedRole_{label}"
            result.suggested_roles[role_name] = ops
            result.confidence[role_name] = float(
                np.mean(support[support >= min_support])
            )
        return result