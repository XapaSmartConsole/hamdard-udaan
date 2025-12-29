from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# load env
load_dotenv()

# FIXED imports (ONLY CHANGE)
from backend.database import engine
from backend.models import Base
from backend.routers import auth, kyc, bank, wallet, kyc_ocr, cart, orders

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(title="RSPL Demo Platform")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
def root():
    return {"status": "RSPL Backend Running"}

# Include routers (UNCHANGED LOGIC)
app.include_router(auth.router)
app.include_router(kyc.router)
app.include_router(bank.router)
app.include_router(wallet.router)
app.include_router(kyc_ocr.router)
app.include_router(cart.router)
app.include_router(orders.router)
