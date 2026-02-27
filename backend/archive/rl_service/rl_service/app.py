from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import uuid
from datetime import datetime
import logging
from rl_agent import RouteRecommendationAgent
import redis
import kafka

app = FastAPI(title="ML & RL Recommendation Service")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize RL Agent
agent = RouteRecommendationAgent()

# Redis for caching
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

# Kafka producer for feedback
producer = kafka.KafkaProducer(
    bootstrap_servers=['kafka:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

class RouteRankingRequest(BaseModel):
    user_id: str
    session_id: str
    candidate_routes: List[Dict]
    user_context: Optional[Dict] = {}

class RouteRankingResponse(BaseModel):
    ranked_routes: List[Dict]
    session_id: str

class FeedbackRequest(BaseModel):
    session_id: str
    user_id: str
    chosen_route_id: Optional[str]
    action: str  # 'booked', 'clicked', 'dismissed'
    context: Optional[Dict] = {}

@app.post("/rank", response_model=RouteRankingResponse)
async def rank_routes(request: RouteRankingRequest):
    """Rank routes using RL agent"""
    try:
        logger.info(f"Ranking routes for user {request.user_id}")

        # Get user context from cache or DB
        user_context = request.user_context or {}

        # Rank routes using RL agent
        ranked_routes = []
        for route in request.candidate_routes:
            # Preprocess state
            state = agent.preprocess_state(user_context, route)

            # Get action (ranking score)
            action = agent.act(state)

            # Add ranking score to route
            route_with_score = route.copy()
            route_with_score['rl_score'] = action
            ranked_routes.append(route_with_score)

        # Sort by RL score (descending)
        ranked_routes.sort(key=lambda x: x['rl_score'], reverse=True)

        # Store ranking in cache for feedback
        ranking_key = f"ranking:{request.session_id}"
        redis_client.setex(ranking_key, 3600, json.dumps(ranked_routes))  # 1 hour

        return RouteRankingResponse(
            ranked_routes=ranked_routes,
            session_id=request.session_id
        )

    except Exception as e:
        logger.error(f"Error ranking routes: {e}")
        raise

@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest, background_tasks: BackgroundTasks):
    """Submit user feedback for learning"""
    try:
        logger.info(f"Received feedback for session {request.session_id}")

        # Get stored ranking
        ranking_key = f"ranking:{request.session_id}"
        stored_ranking = redis_client.get(ranking_key)

        if stored_ranking:
            ranked_routes = json.loads(stored_ranking)

            # Calculate reward
            reward = agent.calculate_reward(
                {'action': request.action, 'chosen_route': request.chosen_route_id},
                ranked_routes,
                request.chosen_route_id
            )

            # Store feedback for training
            feedback_data = {
                'session_id': request.session_id,
                'user_id': request.user_id,
                'chosen_route_id': request.chosen_route_id,
                'action': request.action,
                'reward': reward,
                'ranked_routes': ranked_routes,
                'user_context': request.context or {},
                'timestamp': datetime.utcnow().isoformat()
            }

            # Send to Kafka for processing
            producer.send('rl_feedback', feedback_data)

            # Add to agent's memory for immediate learning
            background_tasks.add_task(process_feedback, feedback_data)

        return {"status": "feedback_received"}

    except Exception as e:
        logger.error(f"Error processing feedback: {e}")
        raise

def process_feedback(feedback_data):
    """Process feedback for RL learning"""
    try:
        # Extract state, action, reward
        user_context = feedback_data['user_context']
        ranked_routes = feedback_data['ranked_routes']
        chosen_route_id = feedback_data['chosen_route_id']
        reward = feedback_data['reward']

        # Find chosen route features
        chosen_route = None
        for route in ranked_routes:
            if route['route_id'] == chosen_route_id:
                chosen_route = route
                break

        if chosen_route:
            # Create state representation
            state = agent.preprocess_state(user_context, chosen_route)

            # For simplicity, assume next state is similar
            next_state = state

            # Add to memory (state, action, reward, next_state, done)
            action = chosen_route.get('rl_score', 0)
            agent.remember(state, action, reward, next_state, True)

            # Train agent
            agent.replay()

    except Exception as e:
        logger.error(f"Error in feedback processing: {e}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent_epsilon": agent.epsilon}

@app.post("/train")
async def train_agent():
    """Trigger agent training"""
    try:
        agent.replay(batch_size=64)
        agent.update_target_model()
        return {"status": "training_completed", "epsilon": agent.epsilon}
    except Exception as e:
        logger.error(f"Training error: {e}")
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
