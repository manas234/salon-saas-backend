from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import json
from datetime import datetime
import uuid

# Line 11: Render ke environment se URL uthaye ga, agar nahi mila toh local sqlite use kare ga
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./salon.db")

# Line 12: Agar sqlite hai toh connect_args use kare ga, warna khaali rahe ga (PostgreSQL ke liye)
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
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
    services_json = Column(String, nullable=True)  # <-- Added to store selected services

try:
    with engine.connect() as conn:
        conn.execute(text("SELECT admin_password FROM salons LIMIT 1"))
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

def find_salon_by_identifier(db: Session, identifier: str):
    if not identifier or identifier == "null":
        return None
    try:
        uuid.UUID(identifier)
        return db.query(Salon).filter(Salon.id == identifier).first()
    except ValueError:
        return db.query(Salon).filter(Salon.slug == identifier).first()

@app.get("/")
def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "FastAPI Salon Backend is running."}

@app.get("/admin.html")
def serve_admin():
    return FileResponse("admin.html")

@app.get("/login.html")
def serve_login():
    if os.path.exists("login.html"):
        return FileResponse("login.html")
    return {"detail": "login file not found"}

@app.get("/super-admin.html")
def serve_superadmin():
    if os.path.exists("super-admin.html"):
        return FileResponse("super-admin.html")
    return {"detail": "super-admin file not found"}

@app.get("/salons")
def get_all_salons(db: Session = Depends(get_db)):
    return [serialize_salon(s) for s in db.query(Salon).all()]

@app.post("/salons")
async def create_salon(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    
    existing = db.query(Salon).filter(Salon.slug == data.get("slug")).first()
    if existing:
        raise HTTPException(status_code=400, detail="Salon with this slug already exists")

    new_salon = Salon(
        id=str(uuid.uuid4()),
        name=data.get("name"),
        address=data.get("address", "Verona, Italy"),
        slug=data.get("slug"),
        opening_time="09:00",
        closing_time="19:00",
        is_active=True,
        admin_password=data.get("admin_password", "admin123"),
        owner_email=data.get("owner_email")
    )
    db.add(new_salon)
    db.commit()
    db.refresh(new_salon)
    return {"status": "success", "salon": serialize_salon(new_salon)}

@app.get("/salons/{identifier}")
def get_salon(identifier: str, db: Session = Depends(get_db)):
    salon = find_salon_by_identifier(db, identifier)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")
    services = db.query(Service).filter(Service.salon_id == salon.id).all()
    return {
        "salon": serialize_salon(salon),
        "services": [{"id": s.id, "name": s.name, "price": s.price, "duration_minutes": s.duration_minutes} for s in services]
    }

@app.put("/salons/{identifier}/settings")
async def update_salon_settings(request: Request, identifier: str, db: Session = Depends(get_db)):
    data = await request.json()
    salon = find_salon_by_identifier(db, identifier)
    if not salon:
        raise HTTPException(status_code=404, detail="Salon not found")
    if "address" in data: salon.address = data["address"]
    if "opening_time" in data: salon.opening_time = data["opening_time"]
    if "closing_time" in data: salon.closing_time = data["closing_time"]
    if "is_active" in data: salon.is_active = data["is_active"]
    db.commit()
    db.refresh(salon)
    return {"status": "success", "salon": serialize_salon(salon)}

@app.get("/services")
def get_services(salon_id: str, db: Session = Depends(get_db)):
    resolved_salon = find_salon_by_identifier(db, salon_id)
    target_id = resolved_salon.id if resolved_salon else salon_id
    services = db.query(Service).filter(Service.salon_id == target_id).all()
    return [{"id": s.id, "name": s.name, "price": s.price, "duration_minutes": s.duration_minutes} for s in services]

@app.post("/services")
async def create_service(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    s_id = data["salon_id"]
    resolved_salon = find_salon_by_identifier(db, s_id)
    final_salon_id = resolved_salon.id if resolved_salon else s_id

    new_service = Service(
        id=str(uuid.uuid4()),
        salon_id=final_salon_id,
        name=data["name"],
        price=data["price"],
        duration_minutes=data["duration_minutes"]
    )
    db.add(new_service)
    db.commit()
    return {"status": "success", "id": new_service.id}

@app.put("/services/{service_id}")
async def update_service(service_id: str, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    service.name = data.get("name", service.name)
    service.price = data.get("price", service.price)
    service.duration_minutes = data.get("duration_minutes", service.duration_minutes)
    db.commit()
    return {"status": "success"}

@app.delete("/services/{service_id}")
def delete_service(service_id: str, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if service:
        db.delete(service)
        db.commit()
    return {"status": "success"}

@app.get("/slots")
def get_slots(salon_id: str = "gnstudio", date: str = None, db: Session = Depends(get_db)):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
        
    salon = find_salon_by_identifier(db, salon_id)
    if not salon:
        salon = db.query(Salon).filter(Salon.slug == "gnstudio").first()
    if not salon:
        return []
    
    slots = []
    open_hour = int(salon.opening_time.split(":")[0]) if salon.opening_time else 9
    close_hour = int(salon.closing_time.split(":")[0]) if salon.closing_time else 19

    if close_hour <= open_hour:
        close_hour += 24

    booked_appointments = db.query(Appointment).filter(
        Appointment.salon_id == salon.id,
        Appointment.appointment_time.like(f"{date}%")
    ).all()
    booked_times = [app.appointment_time.split("T")[1][:5] for app in booked_appointments]

    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute

    for hour in range(open_hour, close_hour):
        actual_hour = hour % 24
        for minute in (0, 30):
            time_str = f"{actual_hour:02d}:{minute:02d}"
            is_booked = time_str in booked_times

            if date == now.strftime("%Y-%m-%d") or date == now.strftime("%m/%d/%Y"):
                if hour < current_hour or (hour == current_hour and current_minute > minute):
                    is_booked = True

            slots.append({
                "time": time_str,
                "is_booked": is_booked
            })
            
    return slots

@app.get("/appointments")
def get_appointments(salon_id: str = None, db: Session = Depends(get_db)):
    query = db.query(Appointment)
    if salon_id:
        resolved_salon = find_salon_by_identifier(db, salon_id)
        target_id = resolved_salon.id if resolved_salon else salon_id
        query = query.filter(Appointment.salon_id == target_id)
    apps = query.all()
    
    result = []
    for a in apps:
        services_list = []
        if a.services_json:
            try:
                services_list = json.loads(a.services_json)
            except:
                pass
                
        result.append({
            "id": a.id,
            "salon_id": a.salon_id,
            "customer_name": a.customer_name,
            "customer_phone": a.customer_phone,
            "customer_email": a.customer_email,
            "appointment_time": a.appointment_time,
            "status": a.status,
            "services": services_list
        })
    return result

@app.post("/appointments")
async def create_appointment(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    
    s_id = data["salon_id"]
    resolved_salon = find_salon_by_identifier(db, s_id)
    final_salon_id = resolved_salon.id if resolved_salon else s_id
    
    services_data = data.get("services", [])
    
    new_app = Appointment(
        id=str(uuid.uuid4()),
        salon_id=final_salon_id,
        customer_name=data["customer_name"],
        customer_phone=data["customer_phone"],
        customer_email=data.get("customer_email"),
        appointment_time=data["appointment_time"],
        status="pending",
        services_json=json.dumps(services_data)
    )
    db.add(new_app)
    db.commit()
    return {"status": "success", "id": new_app.id}

@app.put("/appointments/{app_id}/status")
async def update_appointment_status(app_id: str, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    app = db.query(Appointment).filter(Appointment.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Appointment not found")
    app.status = data.get("status", app.status)
    db.commit()
    return {"status": "success"}

@app.delete("/appointments/{app_id}")
def delete_appointment(app_id: str, db: Session = Depends(get_db)):
    app = db.query(Appointment).filter(Appointment.id == app_id).first()
    if app:
        db.delete(app)
        db.commit()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)