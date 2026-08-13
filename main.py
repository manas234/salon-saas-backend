from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import json
from datetime import datetime

DATABASE_URL = "sqlite:///./salon.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Salon(Base):
    __tablename__ = "salons"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    slug = Column(String, unique=True, index=True)
    opening_time = Column(String, nullable=True, default="09:00")
    closing_time = Column(String, nullable=True, default="19:00")
    is_active = Column(Boolean, nullable=True, default=True)
    admin_password = Column(String, nullable=True, default="admin123")
    owner_email = Column(String, nullable=True)

class Service(Base):
    __tablename__ = "services"
    id = Column(String, primary_key=True, index=True)
    salon_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    duration_minutes = Column(Integer, nullable=False)

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(String, primary_key=True, index=True)
    salon_id = Column(String, nullable=False)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    customer_email = Column(String, nullable=True)
    appointment_time = Column(String, nullable=False)
    status = Column(String, default="pending")
    services_json = Column(String, nullable=True)

try:
    with engine.connect() as conn:
        conn.execute(text("SELECT is_active FROM salons LIMIT 1"))
except Exception:
    Base.metadata.drop_all(bind=engine)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    if not db.query(Salon).filter(Salon.slug == "gnstudio").first():
        db.add(Salon(
            id="71568d45-09f9-4d66-be0b-9789df0a349e", 
            name="GNstudio hair&beauty", 
            address="Via centro 10, Verona, Italy", 
            slug="gnstudio",
            opening_time="09:00",
            closing_time="19:00",
            is_active=True,
            admin_password="admin123"
        ))
        db.commit()
    db.close()

def serialize_salon(salon):
    return {
        "id": salon.id,
        "name": salon.name,
        "address": salon.address,
        "slug": salon.slug,
        "opening_time": salon.opening_time,
        "closing_time": salon.closing_time,
        "is_active": salon.is_active,
        "admin_password": salon.admin_password,
        "owner_email": salon.owner_email
    }

@app.get("/")
def serve_index():
    if os.path.exists("index.html"): return FileResponse("index.html")
    return {"message": "FastAPI Salon Backend is running."}

@app.get("/admin.html")
def serve_admin():
    return FileResponse("admin.html")

@app.get("/superadmin.html")
def serve_superadmin():
    if os.path.exists("superadmin.html"): return FileResponse("superadmin.html")
    return {"detail": "Superadmin file not found"}

@app.get("/salons")
def get_all_salons(db: Session = Depends(get_db)):
    return [serialize_salon(s) for s in db.query(Salon).all()]

@app.post("/salons")
async def create_salon(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    import uuid
    new_salon = Salon(
        id=str(uuid.uuid4()),
        name=data.get("name"),
        slug=data.get("slug"),
        admin_password=data.get("admin_password", "admin123"),
        owner_email=data.get("owner_email"),
        is_active=True
    )
    db.add(new_salon)
    db.commit()
    return {"status": "success"}

@app.put("/salons/{identifier}/settings")
async def update_salon_settings(request: Request, identifier: str, db: Session = Depends(get_db)):
    data = await request.json()
    salon = db.query(Salon).filter((Salon.id == identifier) | (Salon.slug == identifier)).first()
    if not salon: raise HTTPException(status_code=404, detail="Salon not found")
    if "is_active" in data: salon.is_active = data["is_active"]
    db.commit()
    return {"status": "success"}

# ... (baaki functions wese hi rehne dein)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)