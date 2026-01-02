from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models
from routers import auth, kyc, bank, wallet, kyc_ocr, cart, orders
from dotenv import load_dotenv

load_dotenv()

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(title="RSPL Demo Platform")

# Add CORS middleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hamdard-udaan.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:5500"
    ],
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