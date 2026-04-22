"""Small ridge-regression model for remote-share prediction."""

from __future__ import annotations

import numpy as np


class RidgeShareModel:
    def __init__(self, ridge_alpha: float = 1.0):
        if ridge_alpha < 0.0:
            raise ValueError("ridge_alpha must be >= 0")
        self.ridge_alpha = ridge_alpha
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None
        self._weights: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        if x.ndim != 2:
            raise ValueError("x must be a 2D matrix")
        if y.ndim != 1:
            raise ValueError("y must be a 1D vector")
        if x.shape[0] != y.shape[0]:
            raise ValueError("x and y must have the same number of rows")
        if x.shape[0] == 0:
            raise ValueError("Training set is empty")

        mean = np.mean(x, axis=0)
        std = np.std(x, axis=0)
        std[std == 0.0] = 1.0

        z = (x - mean) / std
        z = np.concatenate([np.ones((z.shape[0], 1), dtype=float), z], axis=1)

        reg = np.eye(z.shape[1], dtype=float)
        reg[0, 0] = 0.0

        lhs = z.T @ z + self.ridge_alpha * reg
        rhs = z.T @ y
        weights = np.linalg.solve(lhs, rhs)

        self._mean = mean
        self._std = std
        self._weights = weights

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self._mean is None or self._std is None or self._weights is None:
            raise RuntimeError("Model is not fit")
        if x.ndim != 2:
            raise ValueError("x must be a 2D matrix")

        z = (x - self._mean) / self._std
        z = np.concatenate([np.ones((z.shape[0], 1), dtype=float), z], axis=1)
        pred = z @ self._weights
        return np.clip(pred, 0.0, 1.0)
