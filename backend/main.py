from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers.audit import router as audit_router
from routers.auth import router as auth_router
from routers.candidates import router as candidates_router
from routers.mitigation import router as mitigation_router


app = FastAPI(title="FairFlow AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def health_check():
    return {"status": "FairFlow AI running"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(audit_router, prefix="/audit", tags=["audit"])
app.include_router(candidates_router, tags=["candidates"])
app.include_router(mitigation_router, tags=["mitigation"])
