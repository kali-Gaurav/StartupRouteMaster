from app import create_app
app = create_app()
for route in app.routes:
    print(f"{route.path} - {route.name}")
