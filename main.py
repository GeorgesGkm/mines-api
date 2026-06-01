from datetime import datetime
import os
from fastapi import FastAPI, Depends
from src.core.database import engine, Base,  SessionLocal
from src.auth.router import router as auth_router
from src.auth.dependencies import RoleChecker
from contextlib import asynccontextmanager
from src.mission import models
from src.core.init_db import init_db
from src.auth.router import router as auth_router
from src.users.user_router import router as user_router
from fastapi.middleware.cors import CORSMiddleware
from src.mission.router import router_agent
from src.mission.router import router_mission
from src.mission.router import router_entrep
from src.mission.router import router_proces_verbal
from src.mission.router import router_production
from src.mission.router import router_titre

from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(src: FastAPI):
    # 1. Créer les tables SQL (si elles n'existent pas)
    Base.metadata.create_all(bind=engine)
    
    # 2. Lancer l'initialisation des données
    init_db()
    
    yield
    

app = FastAPI(title="Mines API", lifespan=lifespan)

origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "https://sina-gouv.netlify.src"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "static/notes_explicatives"
os.makedirs(UPLOAD_DIR, exist_ok=True)

UPLOAD_TITRES_DIR = "static/documents_titres"
os.makedirs(UPLOAD_TITRES_DIR, exist_ok=True)

@app.get("/")
def root():
    return {"message": "Backend OK"}

app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="notes_explicatives")
app.mount("/static", StaticFiles(directory=UPLOAD_TITRES_DIR), name="documents_titres")

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(user_router, prefix="/auth", tags=["Gestion des users"])
app.include_router(router_agent.router)
app.include_router(router_mission.router)
app.include_router(router_entrep.router)
app.include_router(router_proces_verbal.router)
app.include_router(router_production.router)
app.include_router(router_titre.router)
