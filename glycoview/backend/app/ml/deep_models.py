import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

from app.ml.features import FEATURE_COLUMNS, TARGET_HORIZONS

# Try importing torch
HAS_TORCH = False
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

class PyTorchGRU(nn.Module if HAS_TORCH else object): # type: ignore
    """PyTorch GRU Neural Network for Multi-Horizon Glucose Forecasting."""
    def __init__(self, input_dim: int, hidden_dim: int = 64, num_layers: int = 2, output_dim: int = 4):
        if not HAS_TORCH:
            return
        super().__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, num_layers, batch_first=True, dropout=0.1)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, output_dim)
        )

    def forward(self, x):
        # x: (batch_size, seq_len=1, input_dim)
        out, _ = self.gru(x)
        out = out[:, -1, :]  # Take last time step
        return self.fc(out)


class DeepPredictor:
    """
    Deep Learning Predictor for Glucose Forecasting.
    Uses PyTorch GRU/LSTM recurrent neural network when available,
    or Scikit-Learn Multi-Layer Perceptron (MLPRegressor) as fallback.
    """
    def __init__(self):
        self.name = "Deep Learning (GRU / Neural Net)"
        self.horizons = TARGET_HORIZONS
        self.is_trained = False
        self.scaler = StandardScaler()
        self.torch_model: Optional[Any] = None
        self.mlp_models: Dict[int, MLPRegressor] = {}
        self.use_torch = HAS_TORCH

    def fit(self, train_df: pd.DataFrame, feature_cols: List[str] = FEATURE_COLUMNS, epochs: int = 25):
        """Fit deep learning network on training data."""
        if train_df.empty:
            return

        X_raw = train_df[feature_cols].values
        # Targets for [15m, 30m, 60m, 120m]
        target_cols = [f'target_{h}m' for h in self.horizons]
        Y_raw = train_df[target_cols].values

        # Clean NaNs
        valid_mask = ~np.isnan(X_raw).any(axis=1) & ~np.isnan(Y_raw).any(axis=1)
        X_clean = X_raw[valid_mask]
        Y_clean = Y_raw[valid_mask]

        if len(X_clean) < 20:
            return

        # Standardize features
        X_scaled = self.scaler.fit_transform(X_clean)

        if self.use_torch and HAS_TORCH:
            try:
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                X_tensor = torch.tensor(X_scaled, dtype=torch.float32).unsqueeze(1).to(device) # (N, 1, input_dim)
                Y_tensor = torch.tensor(Y_clean, dtype=torch.float32).to(device) # (N, 4)

                dataset = TensorDataset(X_tensor, Y_tensor)
                loader = DataLoader(dataset, batch_size=32, shuffle=True)

                self.torch_model = PyTorchGRU(
                    input_dim=len(feature_cols),
                    hidden_dim=64,
                    num_layers=2,
                    output_dim=len(self.horizons)
                ).to(device)

                optimizer = optim.Adam(self.torch_model.parameters(), lr=0.003, weight_decay=1e-4)
                criterion = nn.MSELoss()

                self.torch_model.train()
                for epoch in range(epochs):
                    for bx, by in loader:
                        optimizer.zero_grad()
                        out = self.torch_model(bx)
                        loss = criterion(out, by)
                        loss.backward()
                        optimizer.step()

                self.torch_model.eval()
                self.is_trained = True
                return
            except Exception as e:
                # Fallback to Scikit-Learn MLP if PyTorch training encounters issues
                self.use_torch = False

        # Fallback to Scikit-Learn Multi-Layer Perceptron (MLP)
        for idx, h in enumerate(self.horizons):
            mlp = MLPRegressor(
                hidden_layer_sizes=(64, 32),
                activation='relu',
                solver='adam',
                max_iter=200,
                random_state=42
            )
            mlp.fit(X_scaled, Y_clean[:, idx])
            self.mlp_models[h] = mlp

        self.is_trained = True

    def predict(
        self,
        df: pd.DataFrame,
        feature_cols: List[str] = FEATURE_COLUMNS
    ) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Returns predictions per horizon:
        {horizon: {"p50": np.array, "p10": np.array, "p90": np.array}}
        """
        if not self.is_trained:
            sgv = df['sgv'].values
            return {h: {"p50": sgv, "p10": sgv - 12, "p90": sgv + 12} for h in self.horizons}

        X_raw = df[feature_cols].values
        X_raw = np.nan_to_num(X_raw, nan=0.0)
        X_scaled = self.scaler.transform(X_raw)

        results = {}

        if self.use_torch and HAS_TORCH and self.torch_model is not None:
            try:
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                self.torch_model.eval()
                with torch.no_grad():
                    X_tensor = torch.tensor(X_scaled, dtype=torch.float32).unsqueeze(1).to(device)
                    preds_matrix = self.torch_model(X_tensor).cpu().numpy() # (N, 4)

                for idx, h in enumerate(self.horizons):
                    p50 = np.clip(preds_matrix[:, idx], 30.0, 400.0)
                    # Standard deviation based uncertainty estimation for Deep Neural Net
                    std_est = 10.0 + (h / 5.0) * 1.5
                    p10 = np.clip(p50 - 1.28 * std_est, 30.0, 400.0)
                    p90 = np.clip(p50 + 1.28 * std_est, 30.0, 400.0)
                    results[h] = {"p50": p50, "p10": p10, "p90": p90}
                return results
            except Exception:
                pass

        # MLP Fallback
        for h in self.horizons:
            if h in self.mlp_models:
                p50 = np.clip(self.mlp_models[h].predict(X_scaled), 30.0, 400.0)
                std_est = 10.0 + (h / 5.0) * 1.5
                p10 = np.clip(p50 - 1.28 * std_est, 30.0, 400.0)
                p90 = np.clip(p50 + 1.28 * std_est, 30.0, 400.0)
                results[h] = {"p50": p50, "p10": p10, "p90": p90}
            else:
                sgv = df['sgv'].values
                results[h] = {"p50": sgv, "p10": sgv - 10, "p90": sgv + 10}

        return results

    def save(self, filepath: str):
        """Save deep learning model artifact to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump({
            "mlp_models": self.mlp_models,
            "scaler": self.scaler,
            "is_trained": self.is_trained,
            "use_torch": self.use_torch
        }, filepath)

    def load(self, filepath: str) -> bool:
        """Load deep learning model artifact from disk."""
        if os.path.exists(filepath):
            data = joblib.load(filepath)
            self.mlp_models = data.get("mlp_models", {})
            self.scaler = data.get("scaler", StandardScaler())
            self.is_trained = data.get("is_trained", False)
            self.use_torch = False  # standard joblib fallback
            return True
        return False
