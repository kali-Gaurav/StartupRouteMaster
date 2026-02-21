import time
import json
import random
import uuid
from locust import HttpUser, task, between, events
from websocket import create_connection

class WebSocketUser(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        """Simulate a user connecting to a train tracking stream."""
        self.train_number = f"TRAIN_{random.randint(100, 150)}"
        # Note: In a real test, you would need a valid JWT token
        # For this logic, we assume the server has a 'test_token' bypass or 
        # we generate one if we have the SECRET_KEY.
        self.token = "PROD_HARDENING_TEST_TOKEN" 
        
        ws_url = f"ws://localhost:8000/ws/train/{self.train_number}?token={self.token}"
        try:
            self.ws = create_connection(ws_url)
            print(f"✅ Connected to {self.train_number}")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.ws = None

    @task
    def listen_for_updates(self):
        """Simulates the client receiving position updates."""
        if self.ws:
            try:
                # Set a timeout so we don't block forever
                self.ws.settimeout(1.0)
                result = self.ws.recv()
                data = json.loads(result)
                if data.get("type") == "position_update":
                    events.request_success.fire(
                        request_type="ws_recv",
                        name="position_update",
                        response_time=0,
                        response_length=len(result)
                    )
            except Exception:
                pass # Timeout or other error

    def on_stop(self):
        if self.ws:
            self.ws.close()

class SOSResponder(HttpUser):
    """Simulates a high-priority responder monitoring the system."""
    weight = 1 # Fewer responders than passengers
    
    def on_start(self):
        self.token = "PROD_HARDENING_RESPONDER_TOKEN"
        ws_url = f"ws://localhost:8000/ws/sos?token={self.token}"
        try:
            self.ws = create_connection(ws_url)
        except Exception:
            self.ws = None

    @task
    def monitor_sos(self):
        if self.ws:
            try:
                self.ws.settimeout(2.0)
                result = self.ws.recv()
                events.request_success.fire(
                    request_type="ws_recv_sos",
                    name="sos_alert",
                    response_time=0,
                    response_length=len(result)
                )
            except Exception:
                pass
