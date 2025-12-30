from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine  # NO DOT
import models  # NO DOT
from routers import auth, kyc, bank, wallet, kyc_ocr, cart, orders  # NO DOT
from dotenv import load_dotenv

load_dotenv()

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(title="RSPL Demo Platform")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
def root():
    return {"status": "RSPL Backend Running"}

# Include all routers
app.include_router(auth.router)
app.include_router(kyc.router)
app.include_router(bank.router)
app.include_router(wallet.router)
app.include_router(kyc_ocr.router)
app.include_router(cart.router)
app.include_router(orders.router)