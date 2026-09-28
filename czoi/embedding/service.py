"""Embedding service (E): local embeddings + global alignment functor."""
from __future__ import annotations

import hashlib
import os
from typing import Any

import numpy as np


class EmbeddingService:
    """Local embeddings + trained global alignment functor E_align.

    If `sentence-transformers` is available and `use_transformer=True`,
    embeddings are semantic. Otherwise a deterministic hash embedding is
    used — reproducible and dependency-free.
    """

    def __init__(
        self,
        dimension: int = 64,
        model_name: str = "all-MiniLM-L6-v2",
        use_transformer: bool = False,
    ) -> None:
        self.dimension = dimension
        self.model = None
        if use_transformer:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(model_name)
                self.dimension = self.model.get_sentence_embedding_dimension()
            except ImportError:
                self.model = None
        # Global alignment: a linear map from local to shared space.
        self.alignment_matrix: np.ndarray | None = None

    # -----------------------------------------------------------------
    # Local embeddings
    # -----------------------------------------------------------------
    def embed(self, text: str) -> np.ndarray:
        if self.model is not None:
            return np.asarray(self.model.encode(text, convert_to_numpy=True))
        return self._hash_embed(text)

    def embed_operation(self, operation: Any) -> np.ndarray:
        app = getattr(operation, "application", None)
        app_name = getattr(app, "name", "") if app else ""
        return self.embed(f"{app_name}.{operation.name}")

    def embed_role(self, role: Any) -> np.ndarray:
        if not role.base_permissions:
            return np.zeros(self.dimension)
        vectors = [self.embed_operation(op) for op in role.base_permissions]
        return np.mean(vectors, axis=0)

    # -----------------------------------------------------------------
    # Global alignment functor E_align
    # -----------------------------------------------------------------
    def align_to_global(self, v: np.ndarray) -> np.ndarray:
        v = np.asarray(v, dtype=float)
        if self.alignment_matrix is not None:
            v = v @ self.alignment_matrix
        n = np.linalg.norm(v)
        return v / n if n > 1e-8 else v

    def train_alignment(
        self,
        positives: list[tuple[np.ndarray, np.ndarray]],
        negatives: list[tuple[np.ndarray, np.ndarray]],
        epochs: int = 200,
        lr: float = 0.01,
        margin: float = 0.5,
    ) -> None:
        """Contrastive training of the alignment matrix.

        Objective (paper §5.2):
            sum_positives ||a - b||^2
          - sum_negatives max(0, margin - ||a - b||)^2
        """
        d = self.dimension
        W = np.eye(d)
        for _ in range(epochs):
            grad = np.zeros_like(W)
            for a, b in positives:
                diff = a @ W - b @ W
                grad += 2 * np.outer(a, diff) - 2 * np.outer(b, diff)
            for a, b in negatives:
                diff = a @ W - b @ W
                dist = np.linalg.norm(diff)
                if dist < margin:
                    grad -= 2 * (margin - dist) * (
                        np.outer(a, diff) - np.outer(b, diff)
                    ) / (dist + 1e-8)
            W -= lr * grad / max(len(positives) + len(negatives), 1)
        self.alignment_matrix = W

    # -----------------------------------------------------------------
    # Similarity
    # -----------------------------------------------------------------
    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a = self.align_to_global(a)
        b = self.align_to_global(b)
        return float(np.dot(a, b))

    # -----------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------
    def save_alignment(self, path: str) -> None:
        if self.alignment_matrix is None:
            return
        np.save(path, self.alignment_matrix)

    def load_alignment(self, path: str) -> None:
        if not os.path.exists(path):
            return
        self.alignment_matrix = np.load(path)

    # -----------------------------------------------------------------
    def _hash_embed(self, text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode()).digest()
        raw = np.frombuffer(
            h * ((self.dimension // 32) + 1), dtype=np.uint8
        )[: self.dimension]
        v = (raw.astype(float) - 128.0) / 128.0
        return v