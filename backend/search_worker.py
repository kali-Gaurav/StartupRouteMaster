import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from services.route_engine import route_engine
from database import SessionLocal

logger = logging.getLogger(__name__)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            if route_engine.is_loaded():
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            else:
                self.send_response(503)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "loading"}')
        else:
            self.send_response(404)
            self.end_headers()

def load_graph_background():
    logger.info("Starting background graph loading...")
    db = SessionLocal()
    try:
        route_engine.load_graph_from_db(db)
        logger.info("Background graph loading complete.")
    finally:
        db.close()

def run_worker():
    logger.info("Starting search worker...")

    # Start loading the graph in a background thread
    threading.Thread(target=load_graph_background, daemon=True).start()

    server_address = ('', 8001)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    logger.info(f"Health check server running on port {server_address[1]}...")
    httpd.serve_forever()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_worker()
