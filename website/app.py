"""
website/app.py  —  AutoReels FastAPI backend
Handles auth, Stripe subscriptions, and video generation.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import stripe
import uuid
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add the parent directory so we can import the pipeline
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.script import generate_script
from pipeline.tts import generate_segment_audio
from pipeline.footage import fetch_footage_for_segments
from pipeline.assembler import assemble_video

# ── Config ──────────────────────────────────────────────────
SECRET_KEY        = os.getenv("SECRET_KEY", "autoreels-change-me-" + str(uuid.uuid4()))
ALGORITHM         = "HS256"
TOKEN_EXPIRE_DAYS = 7

STRIPE_SECRET_KEY      = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET  = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID        = os.getenv("STRIPE_PRICE_ID", "")
FRONTEND_URL           = os.getenv("FRONTEND_URL", "http://localhost:8000")

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR   = os.path.join(ROOT, "output")
TEMP_DIR     = os.path.join(ROOT, "temp")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ── Database ─────────────────────────────────────────────────
engine       = create_engine("sqlite:///./autoreels.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()


class User(Base):
    __tablename__ = "users"
    id                 = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email              = Column(String, unique=True, index=True, nullable=False)
    password_hash      = Column(String, nullable=False)
    stripe_customer_id = Column(String, nullable=True)
    is_subscribed      = Column(Boolean, default=False)
    created_at         = Column(DateTime, default=datetime.utcnow)


class Video(Base):
    __tablename__ = "videos"
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id       = Column(String, nullable=False)
    topic         = Column(String, nullable=False)
    status        = Column(String, default="pending")   # pending | generating | done | error
    title         = Column(String, nullable=True)
    output_path   = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

# ── Auth helpers ─────────────────────────────────────────────
pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
security = HTTPBearer(auto_error=False)


def hash_pw(pw: str)  -> str:    return pwd_ctx.hash(pw)
def check_pw(pw, hashed) -> bool: return pwd_ctx.verify(pw, hashed)


def make_token(user_id: str) -> str:
    exp = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def get_db():
    db = SessionLocal()
    try:    yield db
    finally: db.close()


def current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db:    Session                       = Depends(get_db),
):
    if not creds:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Invalid token")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(401, "User not found")
    return user


# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="AutoReels API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)


# ── Schemas ───────────────────────────────────────────────────
class AuthReq(BaseModel):
    email: str
    password: str

class GenReq(BaseModel):
    topic:    str
    duration: int  = 60
    style:    str  = "informative"
    voice:    str  = "alloy"


# ── Auth routes ───────────────────────────────────────────────
@app.post("/api/auth/register")
def register(req: AuthReq, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered")
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user = User(email=req.email, password_hash=hash_pw(req.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"token": make_token(user.id), "email": user.email}


@app.post("/api/auth/login")
def login(req: AuthReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not check_pw(req.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"token": make_token(user.id), "email": user.email, "is_subscribed": user.is_subscribed}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "is_subscribed": user.is_subscribed}


# ── Video pipeline ────────────────────────────────────────────
def run_pipeline(video_id: str, topic: str, duration: int, style: str, voice: str):
    """Background: run the full AI video pipeline for a job."""
    db = SessionLocal()
    try:
        vid = db.query(Video).filter(Video.id == video_id).first()
        vid.status = "generating"; db.commit()

        import shutil
        job_tmp = os.path.join(TEMP_DIR, video_id)
        os.makedirs(job_tmp, exist_ok=True)

        script        = generate_script(topic, duration=duration, style=style)
        audio_files   = generate_segment_audio(script["segments"], job_tmp, voice=voice)
        footage_files = fetch_footage_for_segments(script["segments"], os.getenv("PEXELS_API_KEY"), job_tmp)

        safe = "".join(c for c in script["title"] if c.isalnum() or c in " -_").strip().replace(" ", "_")[:50]
        out  = os.path.join(OUTPUT_DIR, f"{video_id}_{safe}.mp4")

        assemble_video(footage_files=footage_files, audio_files=audio_files,
                       segments=script["segments"], output_path=out)

        vid.status = "done"; vid.title = script["title"]; vid.output_path = out
        db.commit()
        shutil.rmtree(job_tmp, ignore_errors=True)

    except Exception as e:
        vid = db.query(Video).filter(Video.id == video_id).first()
        if vid:
            vid.status = "error"; vid.error_message = str(e); db.commit()
    finally:
        db.close()


@app.post("/api/videos/generate")
def generate(req: GenReq, bg: BackgroundTasks,
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not user.is_subscribed:
        raise HTTPException(403, "Subscription required")
    vid = Video(user_id=user.id, topic=req.topic)
    db.add(vid); db.commit(); db.refresh(vid)
    bg.add_task(run_pipeline, vid.id, req.topic, req.duration, req.style, req.voice)
    return {"video_id": vid.id, "status": "pending"}


@app.get("/api/videos")
def list_videos(user: User = Depends(current_user), db: Session = Depends(get_db)):
    vids = db.query(Video).filter(Video.user_id == user.id).order_by(Video.created_at.desc()).limit(30).all()
    return [{"id": v.id, "topic": v.topic, "title": v.title, "status": v.status,
             "created_at": v.created_at.isoformat(),
             "has_file": bool(v.output_path and os.path.exists(v.output_path))} for v in vids]


@app.get("/api/videos/{vid_id}/status")
def video_status(vid_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    v = db.query(Video).filter(Video.id == vid_id, Video.user_id == user.id).first()
    if not v: raise HTTPException(404, "Not found")
    return {"status": v.status, "title": v.title, "error": v.error_message,
            "has_file": bool(v.output_path and os.path.exists(v.output_path))}


@app.get("/api/videos/{vid_id}/download")
def download(vid_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    v = db.query(Video).filter(Video.id == vid_id, Video.user_id == user.id).first()
    if not v or not v.output_path or not os.path.exists(v.output_path):
        raise HTTPException(404, "File not found")
    return FileResponse(v.output_path, media_type="video/mp4", filename=os.path.basename(v.output_path))


# ── Stripe routes ─────────────────────────────────────────────
@app.post("/api/billing/create-checkout")
def create_checkout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "Stripe not configured — add STRIPE_SECRET_KEY to .env")

    if not user.stripe_customer_id:
        cust = stripe.Customer.create(email=user.email)
        user.stripe_customer_id = cust.id; db.commit()

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        mode="subscription",
        success_url=f"{FRONTEND_URL}/dashboard.html?subscribed=true",
        cancel_url=f"{FRONTEND_URL}/dashboard.html",
    )
    return {"checkout_url": session.url}


@app.post("/api/billing/portal")
def billing_portal(user: User = Depends(current_user)):
    if not user.stripe_customer_id:
        raise HTTPException(400, "No billing account")
    s = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{FRONTEND_URL}/dashboard.html",
    )
    return {"portal_url": s.url}


@app.post("/api/billing/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig     = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid webhook signature")

    cid = event["data"]["object"].get("customer")
    if not cid: return {"ok": True}

    user = db.query(User).filter(User.stripe_customer_id == cid).first()
    if not user: return {"ok": True}

    if event["type"] in ("customer.subscription.created", "customer.subscription.updated"):
        status = event["data"]["object"].get("status")
        user.is_subscribed = status in ("active", "trialing")
        db.commit()
    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        user.is_subscribed = False; db.commit()

    return {"ok": True}


# ── Serve frontend static files ───────────────────────────────
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
