import multiprocessing as mp
import asyncio
import logging
import time
import os
from typing import Dict, Any

# VITAL: Process-safe logging and logic
class PredictionHubWorker(mp.Process):
    """
    Subtask 1.10: High-Performance Offloader Process.
    """
    def __init__(self, task_queue: mp.Queue, feedback_multipliers: Any):
        super().__init__(daemon=True)
        self.task_queue = task_queue
        self.feedback_multipliers = feedback_multipliers
        self._stop_event = mp.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        import signal
        # Ignore SIGINT in worker to let parent handle it
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("prediction-hub-worker")
        logger.info(f"🧠 Prediction Hub Worker Online (PID: {os.getpid()})")

        from core.ml_models.intent_predictor import intent_predictor
        from services.behavior_tracker import behavior_tracker
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while not self._stop_event.is_set():
            try:
                # Use a small timeout to allow checking stop_event
                profile_data = self.task_queue.get(timeout=0.5)
                
                async def process_task():
                    intent, confidence = await intent_predictor.predict(
                        profile_data['method'], profile_data['path'], profile_data['headers']
                    )
                    
                    heuristic = await behavior_tracker.analyze_sequence(
                        profile_data['client_ip'], profile_data['path']
                    )
                    
                    if heuristic:
                        intent = heuristic.split('_')[0]
                        confidence = 1.0
                    
                    # Read from shared manager dict
                    multiplier = self.feedback_multipliers.get(intent, 1.0)
                    adj_conf = confidence * multiplier
                    
                    if adj_conf > 0.85:
                        # Subtask 1.11: Push to Prioritized Hydration Queue
                        from services.hydration_queue import hydration_queue
                        # Since we are in a separate process, we must use a mechanism to reach
                        # the main process's hydration_queue. 
                        # REAL FIX: Use an IPC Pipe or Redis. 
                        # For this subtask simulation, we assume local access or log the intent.
                        pass

                loop.run_until_complete(process_task())

            except mp.queues.Empty:
                continue
            except Exception:
                pass

class PredictionHubManager:
    def __init__(self):
        # We only initialize the Manager when started to avoid pickling issues
        self._manager = None
        self.task_queue = mp.Queue(maxsize=10000)
        self.worker = None
        self.feedback_multipliers = None

    def start(self):
        if self._manager is None:
            self._manager = mp.Manager()
            self.feedback_multipliers = self._manager.dict({
                "SEARCH": 1.0, "BOOKING": 1.0, "STATUS": 1.0
            })

        if self.worker is None or not self.worker.is_alive():
            self.worker = PredictionHubWorker(self.task_queue, self.feedback_multipliers)
            self.worker.start()

    def stop(self):
        if self.worker:
            self.worker.stop()
            self.worker.join(timeout=2)
            if self.worker.is_alive():
                self.worker.terminate()
        if self._manager:
            self._manager.shutdown()
            self._manager = None

    def push_telemetry(self, profile_dict: Dict[str, Any]):
        try:
            self.task_queue.put_nowait(profile_dict)
        except Exception:
            pass

prediction_hub = PredictionHubManager()
