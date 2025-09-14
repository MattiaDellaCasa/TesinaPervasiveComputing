import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import pickle
import os

class SilicaPredictor:
    def __init__(self, data_path="data/mining_data.csv", model_path="models/silica_model.pkl"):
        self.data_path = data_path
        self.model_path = model_path
        self.model = None
        self.feature_columns = [
            '% Iron Feed', '% Silica Feed', 'Starch Flow', 'Amina Flow',
            'Ore Pulp Flow', 'Ore Pulp pH', 'Ore Pulp Density',
            'Flotation Column 01 Air Flow', 'Flotation Column 02 Air Flow',
            'Flotation Column 03 Air Flow', 'Flotation Column 04 Air Flow',
            'Flotation Column 05 Air Flow', 'Flotation Column 06 Air Flow',
            'Flotation Column 07 Air Flow'
        ]
        self.target_column = '% Silica Concentrate'
        
        # Carica o allena modello
        if os.path.exists(self.model_path):
            self.load_model()
        else:
            self.train_model()

    def load_training_data(self):
        """Carica dati reali da CSV"""
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"File dati non trovato: {self.data_path}")
        df = pd.read_csv(self.data_path)
        
        # Controllo colonne
        missing = set(self.feature_columns + [self.target_column]) - set(df.columns)
        if missing:
            raise ValueError(f"Colonne mancanti nel dataset: {missing}")
        
        df = df.dropna(subset=self.feature_columns + [self.target_column])
        return df

    def train_model(self):
        """Allena due modelli e sceglie il migliore"""
        df = self.load_training_data()
        X = df[self.feature_columns]
        y = df[self.target_column]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Pipeline: scaler + modello
        models = {
            'RandomForest': Pipeline([
                ("scaler", StandardScaler()),
                ("regressor", RandomForestRegressor(n_estimators=100, random_state=42))
            ]),
            'GradientBoosting': Pipeline([
                ("scaler", StandardScaler()),
                ("regressor", GradientBoostingRegressor(n_estimators=100, random_state=42))
            ])
        }

        best_model, best_name, best_score = None, None, float("-inf")

        for name, pipeline in models.items():
            scores = cross_val_score(pipeline, X_train, y_train, cv=5, scoring="r2", n_jobs=-1)
            mean_score = scores.mean()
            print(f"{name} - CV R²: {mean_score:.4f} ± {scores.std():.4f}")
            if mean_score > best_score:
                best_score = mean_score
                best_model, best_name = pipeline, name

        # Fit sul train set
        best_model.fit(X_train, y_train)
        y_pred = best_model.predict(X_test)

        # Metriche
        metrics = {
            "r2": r2_score(y_test, y_pred),
            "mse": mean_squared_error(y_test, y_pred),
            "mae": mean_absolute_error(y_test, y_pred),
            "rmse": np.sqrt(mean_squared_error(y_test, y_pred))
        }

        print(f"\nMiglior modello: {best_name}")
        print(f"Metriche: {metrics}")

        self.model = best_model
        self.model_name = best_name
        self.metrics = metrics
        self.save_model()

    def save_model(self):
        os.makedirs(os.path.dirname(self.model_path) or ".", exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "model_name": self.model_name,
                "metrics": self.metrics,
                "features": self.feature_columns,
                "target": self.target_column
            }, f)
        print(f"Modello salvato in {self.model_path}")

    def load_model(self):
        with open(self.model_path, "rb") as f:
            data = pickle.load(f)
        self.model = data["model"]
        self.model_name = data["model_name"]
        self.metrics = data["metrics"]
        self.feature_columns = data["features"]
        self.target_column = data["target"]
        print(f"Modello caricato: {self.model_name}")

    def predict_silica(self, sensor_data: dict):
        if self.model is None:
            raise RuntimeError("Il modello non è caricato o allenato")
        
        # Validazione input
        features = []
        for col in self.feature_columns:
            if col not in sensor_data:
                raise ValueError(f"Feature mancante: {col}")
            features.append(float(sensor_data[col]))

        X = np.array([features])
        return float(self.model.predict(X)[0])