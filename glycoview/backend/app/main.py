from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as data_router
from app.api.analysis_routes import router as analysis_router
from app.api.prediction_routes import router as prediction_router
from app.api.digital_twin_routes import router as twin_router
from app.api.auth_routes import router as auth_router
from app.api.dataset_routes import router as dataset_router

app = FastAPI(title="GlycoView API", version="0.1.0")

# Allow frontend dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(data_router)
app.include_router(analysis_router)
app.include_router(prediction_router)
app.include_router(twin_router)
app.include_router(dataset_router)

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
