from app import app
import json

def list_routes():
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            routes.append({
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods) if hasattr(route, "methods") else []
            })
    
    print(json.dumps(routes, indent=2))

if __name__ == "__main__":
    list_routes()
