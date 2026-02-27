import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from collections import deque
import random
import logging

logger = logging.getLogger(__name__)

# Try to import TensorFlow; if unavailable, fall back to a lightweight heuristic agent
try:
    import tensorflow as tf
    from tensorflow import keras
    _TF_AVAILABLE = True
except Exception:
    _TF_AVAILABLE = False
    logger.info("TensorFlow not available — using fallback lightweight RL stub")


if _TF_AVAILABLE:
    class RouteRecommendationAgent:
        """TensorFlow-backed RL Agent (production/training)."""

        def __init__(self, state_size=10, action_size=5, learning_rate=0.001):
            self.state_size = state_size
            self.action_size = action_size
            self.learning_rate = learning_rate
            self.gamma = 0.95
            self.epsilon = 1.0
            self.epsilon_min = 0.01
            self.epsilon_decay = 0.995
            self.memory = deque(maxlen=2000)

            self.model = self._build_model()
            self.target_model = self._build_model()
            self.update_target_model()

        def _build_model(self):
            model = keras.Sequential([
                keras.layers.Dense(24, input_dim=self.state_size, activation='relu'),
                keras.layers.Dense(24, activation='relu'),
                keras.layers.Dense(self.action_size, activation='linear')
            ])
            model.compile(loss='mse', optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate))
            return model

        def update_target_model(self):
            self.target_model.set_weights(self.model.get_weights())

        def remember(self, state, action, reward, next_state, done):
            self.memory.append((state, action, reward, next_state, done))

        def act(self, state):
            if np.random.rand() <= self.epsilon:
                return random.randrange(self.action_size)
            act_values = self.model.predict(state, verbose=0)
            return np.argmax(act_values[0])

        def replay(self, batch_size=32):
            if len(self.memory) < batch_size:
                return
            minibatch = random.sample(self.memory, batch_size)
            for state, action, reward, next_state, done in minibatch:
                target = reward
                if not done:
                    target = reward + self.gamma * np.amax(self.target_model.predict(next_state, verbose=0)[0])
                target_f = self.model.predict(state, verbose=0)
                target_f[0][action] = target
                self.model.fit(state, target_f, epochs=1, verbose=0)
            if self.epsilon > self.epsilon_min:
                self.epsilon *= self.epsilon_decay

        def load(self, name):
            self.model.load_weights(name)

        def save(self, name):
            self.model.save_weights(name)

        def preprocess_state(self, user_context, route_features):
            state = np.array([
                user_context.get('past_bookings', 0),
                route_features.get('duration', 0),
                route_features.get('cost', 0),
                route_features.get('transfers', 0),
                route_features.get('comfort_score', 0),
                user_context.get('preferred_time', 0),
                route_features.get('reliability', 0),
                user_context.get('budget_sensitivity', 0),
                route_features.get('popularity', 0),
                user_context.get('loyalty_points', 0)
            ]).reshape(1, -1)
            scaler = StandardScaler()
            state = scaler.fit_transform(state)
            return state

        def calculate_reward(self, user_action, recommended_routes, chosen_route):
            if not chosen_route:
                return -1
            chosen_index = None
            for i, route in enumerate(recommended_routes):
                if route['route_id'] == chosen_route:
                    chosen_index = i
                    break
            if chosen_index is None:
                return -1
            rank_reward = (len(recommended_routes) - chosen_index) / len(recommended_routes)
            satisfaction_reward = 0
            if user_action.get('booking_confirmed'):
                satisfaction_reward += 1
            if user_action.get('saved_to_favorites'):
                satisfaction_reward += 0.5
            total_reward = rank_reward + satisfaction_reward
            return min(total_reward, 2.0)


else:
    class RouteRecommendationAgent:
        """Lightweight fallback agent used for development when TensorFlow is not installed.
        - Provides same public API as the TF agent (act, remember, replay, preprocess_state, calculate_reward).
        - Uses simple heuristic scoring and lightweight memory; avoids heavy ML deps so dev integration works.
        """

        def __init__(self, state_size=10, action_size=5, learning_rate=0.001):
            self.state_size = state_size
            self.action_size = action_size
            self.epsilon = 0.1  # small exploration for dev
            self.memory = deque(maxlen=500)

        def remember(self, state, action, reward, next_state, done):
            self.memory.append((state, action, reward, next_state, done))

        def act(self, state):
            # Dev heuristic: use a deterministic weighted sum of state features as score
            # return a score between 0..1 for ranking (higher is better)
            arr = np.asarray(state).reshape(-1)
            score = float(np.tanh(np.sum(arr) / (len(arr) + 1)))
            return score

        def replay(self, batch_size=32):
            # No-op for fallback
            return

        def preprocess_state(self, user_context, route_features):
            state = np.array([
                user_context.get('past_bookings', 0),
                route_features.get('duration', 0),
                route_features.get('cost', 0),
                route_features.get('transfers', 0),
                route_features.get('comfort_score', 0),
                user_context.get('preferred_time', 0),
                route_features.get('reliability', 0),
                user_context.get('budget_sensitivity', 0),
                route_features.get('popularity', 0),
                user_context.get('loyalty_points', 0)
            ]).reshape(1, -1)
            # simple normalization
            denom = np.linalg.norm(state) if np.linalg.norm(state) > 0 else 1.0
            return state / denom

        def calculate_reward(self, user_action, recommended_routes, chosen_route):
            if not chosen_route:
                return -1
            chosen_index = None
            for i, route in enumerate(recommended_routes):
                if route['route_id'] == chosen_route:
                    chosen_index = i
                    break
            if chosen_index is None:
                return -1
            rank_reward = (len(recommended_routes) - chosen_index) / len(recommended_routes)
            satisfaction_reward = 0
            if user_action.get('booking_confirmed'):
                satisfaction_reward += 1
            total_reward = rank_reward + satisfaction_reward
            return min(total_reward, 2.0)
