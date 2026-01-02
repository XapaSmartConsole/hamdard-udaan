from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from database import get_db
from models import Bank
import openai
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/bank", tags=["Bank"])
openai.api_key = os.getenv("OPENAI_API_KEY", "your-openai-api-key-here")


# ============================================================
# ADD / UPDATE BANK + UPI DETAILS (NON-DESTRUCTIVE)
# ============================================================
@router.post("/add")
def add_or_update_payment_method(
    user_id: int = Form(...),
    payment_method: str = Form(default="BANK"),

    # Bank fields
    account_holder_name: str = Form(None),
    bank_name: str = Form(None),
    account_number: str = Form(None),
    ifsc: str = Form(None),
    cheque_image: str = Form(None),

    # UPI fields
    upi_id: str = Form(None),
    upi_qr_code: str = Form(None),

    db: Session = Depends(get_db)
):
    """
    Save BOTH Bank & UPI details.
    payment_method only decides which one is ACTIVE.
    """

    # Validate only the selected method
    if payment_method == "BANK":
        if not all([account_holder_name, bank_name, account_number, ifsc]):
            raise HTTPException(status_code=400, detail="All bank details are required")
    elif payment_method == "UPI":
        if not upi_id:
            raise HTTPException(status_code=400, detail="UPI ID is required")
        if not re.match(r'^[\w\.\-]+@[\w]+$', upi_id):
            raise HTTPException(status_code=400, detail="Invalid UPI ID format")
    else:
        raise HTTPException(status_code=400, detail="Invalid payment method")

    bank = db.query(Bank).filter(Bank.user_id == user_id).first()

    if not bank:
        bank = Bank(user_id=user_id)
        db.add(bank)

    # 🔥 DO NOT DELETE OTHER METHOD DATA
    bank.payment_method = payment_method

    # Update BANK fields if provided
    if account_holder_name:
        bank.account_holder_name = account_holder_name
    if bank_name:
        bank.bank_name = bank_name
    if account_number:
        bank.account_number = account_number
    if ifsc:
        bank.ifsc = ifsc
    if cheque_image:
        bank.cheque_image = cheque_image

    # Update UPI fields if provided
    if upi_id:
        bank.upi_id = upi_id
    if upi_qr_code:
        bank.upi_qr_code = upi_qr_code

    # Reset validation when data changes
    bank.is_validated = False
    bank.validation_status = "PENDING"

    db.commit()

    return {
        "success": True,
        "message": "Payment details saved successfully",
        "payment_method": payment_method
    }


# ============================================================
# GET PAYMENT DETAILS (RETURN BOTH BANK + UPI)
# ============================================================
@router.get("")
def get_payment_details(user_id: int, db: Session = Depends(get_db)):
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()

    if not bank:
        raise HTTPException(status_code=404, detail="Payment details not found")

    return {
        "user_id": bank.user_id,
        "payment_method": bank.payment_method,
        "is_validated": bank.is_validated,
        "validation_status": bank.validation_status,

        # Bank data
        "account_holder_name": bank.account_holder_name,
        "bank_name": bank.bank_name,
        "account_number": bank.account_number,
        "ifsc": bank.ifsc,
        "cheque_image": bank.cheque_image,

        # UPI data
        "upi_id": bank.upi_id,
        "upi_qr_code": bank.upi_qr_code
    }


# ============================================================
# VALIDATE SELECTED PAYMENT METHOD
# ============================================================
@router.post("/validate")
async def validate_payment_method(user_id: int, db: Session = Depends(get_db)):
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()

    if not bank:
        raise HTTPException(status_code=404, detail="Payment details not found")

    if bank.is_validated:
        return {
            "message": "Payment method already validated",
            "is_validated": True,
            "validation_status": "VALIDATED"
        }

    if bank.payment_method == "BANK":
        return await validate_bank_account_internal(bank, db)
    else:
        return await validate_upi_internal(bank, db)


# ============================================================
# BANK VALIDATION (CHEQUE OCR)
# ============================================================
async def validate_bank_account_internal(bank, db):
    if not bank.cheque_image:
        raise HTTPException(status_code=400, detail="Cheque image required")

    base64_image = bank.cheque_image.split(",")[1] if bank.cheque_image.startswith("data:image") else bank.cheque_image

    extracted = await extract_bank_details_from_cheque(base64_image)

    result = validate_extracted_details(
        extracted,
        {
            "account_holder_name": bank.account_holder_name,
            "account_number": bank.account_number,
            "ifsc": bank.ifsc
        }
    )

    if not result["is_valid"]:
        bank.validation_status = "FAILED"
        db.commit()
        raise HTTPException(status_code=400, detail=result["reason"])

    bank.is_validated = True
    bank.validation_status = "VALIDATED"
    db.commit()

    return {
        "message": "✅ Bank account validated successfully",
        "is_validated": True,
        "matched_fields": result["matched_fields"]
    }


# ============================================================
# UPI VALIDATION
# ============================================================
async def validate_upi_internal(bank, db):
    if not bank.upi_id:
        raise HTTPException(status_code=400, detail="UPI ID missing")

    if not re.match(r'^[\w\.\-]+@[\w]+$', bank.upi_id):
        bank.validation_status = "FAILED"
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid UPI ID format")

    bank.is_validated = True
    bank.validation_status = "VALIDATED"
    db.commit()

    return {
        "message": "✅ UPI validated successfully",
        "is_validated": True,
        "upi_id": bank.upi_id
    }


# ============================================================
# OCR EXTRACTION (UNCHANGED)
# ============================================================
async def extract_bank_details_from_cheque(base64_image: str) -> dict:
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract bank details from this cheque and return JSON only."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        max_tokens=500,
        temperature=0
    )

    content = response.choices[0].message.content
    return json.loads(content[content.find("{"):content.rfind("}") + 1])


# ============================================================
# MATCHING LOGIC (UNCHANGED)
# ============================================================
def validate_extracted_details(extracted: dict, stored: dict) -> dict:
    def normalize(s):
        return re.sub(r'[^A-Z0-9]', '', s.upper()) if s else ""

    errors, matched = [], []

    if normalize(extracted.get("account_holder_name")) == normalize(stored.get("account_holder_name")):
        matched.append("Account holder name matched")
    else:
        errors.append("Account holder name mismatch")

    if normalize(extracted.get("account_number")) == normalize(stored.get("account_number")):
        matched.append("Account number matched")
    else:
        errors.append("Account number mismatch")

    if normalize(extracted.get("ifsc")) == normalize(stored.get("ifsc")):
        matched.append("IFSC matched")
    else:
        errors.append("IFSC mismatch")

    return {
        "is_valid": len(errors) == 0,
        "matched_fields": matched,
        "reason": "\n".join(errors)
    }

@router.post("/update-method")
def update_payment_method(
    user_id: int = Form(...),
    payment_method: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update only the active payment method"""
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()
    
    if not bank:
        raise HTTPException(status_code=404, detail="Payment details not found")
    
    bank.payment_method = payment_method
    db.commit()
    
    return {"success": True, "payment_method": payment_method}

def calculate_similarity(s1: str, s2: str) -> float:
    """
    Calculate similarity using Levenshtein distance
    """
    if not s1 or not s2:
        return 0.0
    
    if s1 == s2:
        return 1.0
    
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    
    len1, len2 = len(s1), len(s2)
    current_row = list(range(len1 + 1))
    
    for i in range(1, len2 + 1):
        previous_row, current_row = current_row, [i] + [0] * len1
        for j in range(1, len1 + 1):
            add = previous_row[j] + 1
            delete = current_row[j - 1] + 1
            change = previous_row[j - 1]
            if s1[j - 1] != s2[i - 1]:
                change += 1
            current_row[j] = min(add, delete, change)
    
    distance = current_row[len1]
    max_len = max(len(s1), len(s2))
    similarity = 1 - (distance / max_len) if max_len > 0 else 0.0
    
    return similarity