import logging
import pandas as pd
import xgboost as xgb
import pickle
import os
from sqlalchemy.orm import Session
from database.models import DemandTrainingData
from datetime import datetime

logger = logging.getLogger("routemaster.ml.trainer")

class DemandTrainingManager:
    """
    [Neural Brain] The Training Manager.
    Handles the end-to-end ML training lifecycle.
    """
    ARTIFACT_PATH = "backend/services/ml/artifacts/demand_model.pkl"

    def __init__(self, db: Session):
        self.db = db
        os.makedirs(os.path.dirname(self.ARTIFACT_PATH), exist_ok=True)

    def train_demand_model(self):
        """Fetches data, trains XGBoost, and saves the artifact."""
        logger.info("Fetching training data...")
        
        # Load data
        query = self.db.query(DemandTrainingData)
        df = pd.read_sql(query.statement, self.db.bind)
        
        if len(df) < 100:
            raise ValueError("Not enough training data. Need at least 100 events.")
            
        # Feature Engineering
        # Map origin/destination to categorical codes
        df['origin_cat'] = df['origin'].astype('category').cat.codes
        df['dest_cat'] = df['destination'].astype('category').cat.codes
        
        X = df[['origin_cat', 'dest_cat', 'hour', 'day_of_week']]
        y = df['demand_score']
        
        logger.info(f"Training XGBoost model on {len(df)} samples...")
        
        # Simple XGBoost Regressor
        model = xgb.XGBRegressor(objective='reg:squarederror', n_estimators=100)
        model.fit(X, y)
        
        # Persist model
        with open(self.ARTIFACT_PATH, 'wb') as f:
            pickle.dump({
                "model": model,
                "mappings": {
                    "origin": df['origin'].astype('category').cat.categories.tolist(),
                    "dest": df['destination'].astype('category').cat.categories.tolist()
                }
            }, f)
            
        logger.info(f"🚀 Model trained and saved to {self.ARTIFACT_PATH}")
        return {"status": "success", "samples": len(df)}

demand_trainer = DemandTrainingManager
