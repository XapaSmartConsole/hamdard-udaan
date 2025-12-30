from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from database import get_db
from models import User
import random
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["Auth"])

class ProfileUpdateModel(BaseModel):
    user_id: int
    profile_picture: str = None
    be_name: str = None
    outlet_name: str = None  # ✅ NEW
    region: str = None
    state: str = None
    city: str = None
    address: str = None
    pincode: str = None
    member_type: str = None
    slab: str = None
    distributor_name: str = None
    target: int = None

def generate_ham_code(db: Session) -> str:
    """Generate unique HAM code in format HAM002665"""
    while True:
        # Get the highest existing HAM code number
        last_user = db.query(User).filter(
            User.ham_code.isnot(None)
        ).order_by(User.id.desc()).first()
        
        if last_user and last_user.ham_code:
            # Extract number from HAM002665 format
            try:
                last_number = int(last_user.ham_code.replace("HAM", ""))
                new_number = last_number + 1
            except:
                new_number = 1
        else:
            new_number = 1
        
        # Format as HAM000001, HAM000002, etc.
        ham_code = f"HAM{new_number:06d}"
        
        # Check if this code already exists (safety check)
        existing = db.query(User).filter(User.ham_code == ham_code).first()
        if not existing:
            return ham_code

@router.post("/signup")
def signup(full_name: str, phone: str, email: str = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == phone).first()
    if user:
        return {"status": "exists"}

    # ✅ Generate HAM code on signup
    ham_code = generate_ham_code(db)
    
    user = User(
        full_name=full_name, 
        phone=phone, 
        email=email,
        ham_code=ham_code
    )
    db.add(user)
    db.commit()
    return {"status": "created", "ham_code": ham_code}


@router.post("/send-otp")
def send_otp(phone: str, db: Session = Depends(get_db)):
    otp = str(random.randint(100000, 999999))

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        return {"error": "User not found"}

    user.otp = otp
    db.commit()

    # 🔥 DEMO MODE - Log OTP
    print(f"=" * 50)
    print(f"📱 OTP SENT TO: {phone}")
    print(f"🔐 OTP CODE: {otp}")
    print(f"=" * 50)
    
    # ⚠️ Return OTP in response (ONLY FOR DEMO - Remove in production!)
    return {"message": "OTP sent successfully", "demo_otp": otp}


@router.post("/verify-otp")
def verify_otp(phone: str, otp: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.phone == phone,
        User.otp == otp
    ).first()

    if not user:
        return {"success": False}

    user.otp_verified = True
    user.otp = None
    
    # ✅ Generate HAM code if not exists (for old users)
    if not user.ham_code:
        user.ham_code = generate_ham_code(db)
    
    db.commit()

    return {"success": True, "user_id": user.id, "ham_code": user.ham_code}

@router.get("/user/profile")
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {"error": "User not found"}

    # ✅ Check if profile is complete
    is_complete = all([
        user.be_name,
        user.outlet_name,  # ✅ NEW: Include Outlet Name in completion check
        user.member_type,
        user.slab,
        user.distributor_name,
        user.target is not None,
        user.address,
        user.pincode,
        user.region,
        user.state,
        user.city
    ])

    return {
        "id": user.id,
        "ham_code": user.ham_code,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "profile_picture": user.profile_picture,
        "be_name": user.be_name,
        "outlet_name": user.outlet_name,  # ✅ NEW
        "region": user.region,
        "state": user.state,
        "city": user.city,
        "address": user.address,
        "pincode": user.pincode,
        "member_type": user.member_type,
        "slab": user.slab,
        "distributor_name": user.distributor_name,
        "target": user.target,
        "is_profile_complete": is_complete
    }

@router.post("/user/update-profile")
def update_user_profile(data: ProfileUpdateModel, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == data.user_id).first()
    
    if not user:
        return {"success": False, "error": "User not found"}
    
    # Update existing fields
    if data.profile_picture:
        user.profile_picture = data.profile_picture
    if data.be_name:
        user.be_name = data.be_name
    if data.outlet_name:  # ✅ NEW
        user.outlet_name = data.outlet_name
    if data.region:
        user.region = data.region
    if data.state:
        user.state = data.state
    if data.city:
        user.city = data.city
    if data.address:
        user.address = data.address
    if data.pincode:
        user.pincode = data.pincode
    if data.member_type:
        user.member_type = data.member_type
    if data.slab:
        user.slab = data.slab
    if data.distributor_name:
        user.distributor_name = data.distributor_name
    if data.target is not None:
        user.target = data.target
    
    db.commit()
    
    return {"success": True, "message": "Profile updated successfully"}