from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as data_router
from app.api.analysis_routes import router as analysis_router
from app.api.prediction_routes import router as prediction_router
from app.api.digital_twin_routes import router as twin_router

app = FastAPI(title="GlycoView API", version="0.1.0")

# Allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data_router)
app.include_router(analysis_router)
app.include_router(prediction_router)
app.include_router(twin_router)

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
