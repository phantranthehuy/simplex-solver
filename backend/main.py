from fastapi import FastAPI

try:
    from .api.simplex_router import router
except ImportError:
    from api.simplex_router import router

app = FastAPI(
    title="Hybrid Simplex Engine API", 
    description="Hệ thống giải tích đơn hình 2 pha tích hợp cho Giáo dục và Môi trường Công nghiệp", 
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Hybrid Simplex Engine API. Please use POST /api/v1/simplex/solve"}
