from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
app.add_middleware(CORSMiddleware, allow_origins=['*'])

print('user_middleware length =', len(app.user_middleware))
for i, item in enumerate(app.user_middleware):
    print(f'[{i}] type={type(item)!r} repr={item!r} iter(tuple(item)) ->', tuple(item))

print('\nmiddleware combined list:')
middleware = [item for item in app.user_middleware]
print(middleware)
