
import os
import pickle
import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

def create_models():
    # Ensure models directory exists
    os.makedirs("models", exist_ok=True)
    
    # 1. Tatkal Demand Model
    tatkal_model_path = "models/tatkal_demand_model.pkl"
    if not os.path.exists(tatkal_model_path):
        print("Creating scaffold Tatkal Demand Model...")
        # Simple RF model: hours_to_departure, booking_velocity, route_popularity, 
        # seasonality, day_of_week, month, is_holiday, occupancy, price_premium, competition
        X = np.random.rand(100, 10)
        y = np.random.rand(100)
        model = RandomForestRegressor(n_estimators=10)
        model.fit(X, y)
        with open(tatkal_model_path, 'wb') as f:
            pickle.dump(model, f)
        print(f"v Saved to {tatkal_model_path}")
    else:
        print(f"Tatkal model already exists at {tatkal_model_path}")

    # 2. Route Ranking Model
    route_model_path = "models/route_ranking_model.pkl"
    if not os.path.exists(route_model_path):
        print("Creating scaffold Route Ranking Model...")
        # Simple RF model: duration_mins, price, reliability_score, popularity, convenience_score
        X = np.random.rand(100, 5)
        y = np.random.rand(100)
        model = RandomForestRegressor(n_estimators=10)
        model.fit(X, y)
        joblib.dump(model, route_model_path)
        print(f"v Saved to {route_model_path}")
    else:
        print(f"Route ranking model already exists at {route_model_path}")

if __name__ == "__main__":
    create_models()
