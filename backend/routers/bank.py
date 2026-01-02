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
# ADD / UPDATE BANK OR UPI DETAILS
# ============================================================
@router.post("/add")
def add_or_update_payment_method(
    user_id: int = Form(...),
    payment_method: str = Form(default="BANK"),  # ✅ FIXED: Default to BANK
    
    # Bank fields (optional if UPI)
    account_holder_name: str = Form(None),
    bank_name: str = Form(None),
    account_number: str = Form(None),
    ifsc: str = Form(None),
    cheque_image: str = Form(None),
    
    # UPI fields (optional if BANK)
    upi_id: str = Form(None),
    upi_qr_code: str = Form(None),
    
    db: Session = Depends(get_db)
):
    """
    Add or update payment method (Bank or UPI)
    """
    
    # Validate based on payment method
    if payment_method == "BANK":
        if not all([account_holder_name, bank_name, account_number, ifsc, cheque_image]):
            raise HTTPException(status_code=400, detail="All bank details are required")
    elif payment_method == "UPI":
        if not upi_id:
            raise HTTPException(status_code=400, detail="UPI ID is required")
        
        if not re.match(r'^[\w\.\-]+@[\w]+$', upi_id):
            raise HTTPException(status_code=400, detail="Invalid UPI ID format")
    else:
        raise HTTPException(status_code=400, detail="Invalid payment method")

    # Check if payment details already exist
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()

    if bank:
        # Update existing
        bank.payment_method = payment_method
        
        if payment_method == "BANK":
            bank.account_holder_name = account_holder_name
            bank.bank_name = bank_name
            bank.account_number = account_number
            bank.ifsc = ifsc
            bank.cheque_image = cheque_image
            bank.upi_id = None
            bank.upi_qr_code = None
        else:  # UPI
            bank.upi_id = upi_id
            bank.upi_qr_code = upi_qr_code
            bank.account_holder_name = account_holder_name
            bank.bank_name = None
            bank.account_number = None
            bank.ifsc = None
            bank.cheque_image = None
        
        bank.is_validated = False
        bank.validation_status = "PENDING"
    else:
        # Create new
        bank_data = {
            "user_id": user_id,
            "payment_method": payment_method,
            "is_validated": False,
            "validation_status": "PENDING"
        }
        
        if payment_method == "BANK":
            bank_data.update({
                "account_holder_name": account_holder_name,
                "bank_name": bank_name,
                "account_number": account_number,
                "ifsc": ifsc,
                "cheque_image": cheque_image
            })
        else:  # UPI
            bank_data.update({
                "upi_id": upi_id,
                "upi_qr_code": upi_qr_code,
                "account_holder_name": account_holder_name
            })
        
        bank = Bank(**bank_data)
        db.add(bank)

    db.commit()

    return {
        "success": True,
        "message": f"{payment_method} details saved successfully",
        "payment_method": payment_method
    }


# ============================================================
# GET PAYMENT DETAILS (BANK OR UPI)
# ============================================================
@router.get("")
def get_payment_details(
    user_id: int,
    db: Session = Depends(get_db)
):
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()

    if not bank:
        raise HTTPException(status_code=404, detail="Payment details not found")

    response = {
        "user_id": bank.user_id,
        "payment_method": bank.payment_method if hasattr(bank, 'payment_method') else "BANK",
        "is_validated": bank.is_validated if hasattr(bank, 'is_validated') else False,
        "validation_status": bank.validation_status if hasattr(bank, 'validation_status') else "PENDING"
    }
    
    if bank.payment_method == "BANK":
        response.update({
            "account_holder_name": bank.account_holder_name,
            "bank_name": bank.bank_name,
            "account_number": bank.account_number,
            "ifsc": bank.ifsc,
            "cheque_image": bank.cheque_image
        })
    else:  # UPI
        response.update({
            "upi_id": bank.upi_id,
            "upi_qr_code": bank.upi_qr_code if hasattr(bank, 'upi_qr_code') else None,
            "account_holder_name": bank.account_holder_name if bank.account_holder_name else None
        })

    return response


# ============================================================
# VALIDATE PAYMENT METHOD (BANK OR UPI)
# ============================================================
@router.post("/validate")
async def validate_payment_method(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Validate payment method (Bank with AI OCR or UPI with basic checks)
    """
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()
    
    if not bank:
        raise HTTPException(status_code=404, detail="Payment details not found")
    
    if hasattr(bank, 'is_validated') and bank.is_validated:
        return {
            "message": "Payment method already validated",
            "is_validated": True,
            "validation_status": "VALIDATED"
        }
    
    try:
        if bank.payment_method == "BANK":
            return await validate_bank_account_internal(bank, db)
        else:  # UPI
            return await validate_upi_internal(bank, db)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Validation error: {str(e)}")
        
        if hasattr(bank, 'validation_status'):
            bank.validation_status = "FAILED"
            db.commit()
        
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )


# ============================================================
# INTERNAL: VALIDATE BANK ACCOUNT (AI-POWERED)
# ============================================================
async def validate_bank_account_internal(bank, db):
    """
    AI-powered bank account validation using cheque image
    """
    if not bank.cheque_image:
        raise HTTPException(status_code=400, detail="Cheque image is required for validation")
    
    if bank.cheque_image.startswith("data:image"):
        base64_image = bank.cheque_image.split(",")[1]
    else:
        base64_image = bank.cheque_image
    
    extracted_details = await extract_bank_details_from_cheque(base64_image)
    
    validation_result = validate_extracted_details(
        extracted_details,
        {
            "account_holder_name": bank.account_holder_name,
            "account_number": bank.account_number,
            "ifsc": bank.ifsc
        }
    )
    
    if validation_result["is_valid"]:
        bank.is_validated = True
        bank.validation_status = "VALIDATED"
        db.commit()
        
        return {
            "message": "✅ Bank account validated successfully!",
            "is_validated": True,
            "validation_status": "VALIDATED",
            "matched_fields": validation_result.get("matched_fields", [])
        }
    else:
        bank.is_validated = False
        bank.validation_status = "FAILED"
        db.commit()
        
        raise HTTPException(
            status_code=400,
            detail=f"Validation failed: {validation_result['reason']}"
        )


# ============================================================
# INTERNAL: VALIDATE UPI
# ============================================================
async def validate_upi_internal(bank, db):
    """
    Basic UPI validation (format check)
    """
    if not bank.upi_id:
        raise HTTPException(status_code=400, detail="UPI ID is required")
    
    upi_pattern = r'^[\w\.\-]+@[\w]+$'
    
    if not re.match(upi_pattern, bank.upi_id):
        bank.is_validated = False
        bank.validation_status = "FAILED"
        db.commit()
        
        raise HTTPException(
            status_code=400,
            detail="Invalid UPI ID format. Expected format: username@bankname"
        )
    
    bank.is_validated = True
    bank.validation_status = "VALIDATED"
    db.commit()
    
    return {
        "message": "✅ UPI ID validated successfully!",
        "is_validated": True,
        "validation_status": "VALIDATED",
        "upi_id": bank.upi_id
    }


# ============================================================
# HELPER: EXTRACT BANK DETAILS FROM CHEQUE USING OPENAI
# ============================================================
async def extract_bank_details_from_cheque(base64_image: str) -> dict:
    """
    Use OpenAI Vision API to extract bank details from cancelled cheque image
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are a bank document OCR specialist. Extract the following details from this cancelled cheque image:

1. Account holder name (exactly as printed on cheque)
2. Account number (numeric only, no spaces or special characters)
3. IFSC code (11 characters, format: XXXX0XXXXXX)
4. Bank name

IMPORTANT INSTRUCTIONS:
- Extract text EXACTLY as it appears
- For account number: extract all digits, remove spaces/dashes
- For IFSC: ensure it's 11 characters
- For name: extract the exact name printed on the cheque

Return ONLY a valid JSON object with these exact keys:
{
    "account_holder_name": "EXACT NAME FROM CHEQUE",
    "account_number": "DIGITS ONLY",
    "ifsc": "11 CHAR IFSC CODE",
    "bank_name": "BANK NAME"
}

If you cannot find any field with high confidence, use "NOT_FOUND" as the value.
Do not include any additional text, explanations, or formatting - ONLY the JSON object."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0
        )
        
        content = response.choices[0].message.content.strip()
        print(f"🤖 OpenAI Response: {content}")
        
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        
        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            extracted_data = json.loads(json_str)
            print(f"✅ Extracted data: {extracted_data}")
            return extracted_data
        else:
            raise ValueError("No valid JSON found in OpenAI response")
    
    except Exception as e:
        print(f"❌ OpenAI extraction error: {str(e)}")
        raise Exception(f"Failed to extract details from cheque: {str(e)}")


# ============================================================
# HELPER: VALIDATE EXTRACTED DETAILS
# ============================================================
def validate_extracted_details(extracted: dict, stored: dict) -> dict:
    """
    Compare extracted details with stored details
    """
    errors = []
    matched_fields = []
    
    def normalize(s):
        if not s or s == "NOT_FOUND":
            return None
        return re.sub(r'[^A-Z0-9]', '', str(s).upper())
    
    extracted_name = normalize(extracted.get("account_holder_name", ""))
    stored_name = normalize(stored.get("account_holder_name", ""))
    
    if not extracted_name:
        errors.append("❌ Account holder name not found in cheque image")
    else:
        similarity = calculate_similarity(extracted_name, stored_name)
        if similarity >= 0.75:
            matched_fields.append("✅ Account holder name matched")
        else:
            errors.append(
                f"❌ Account holder name mismatch\n"
                f"   Expected: {stored['account_holder_name']}\n"
                f"   Found: {extracted.get('account_holder_name')}"
            )
    
    extracted_account = normalize(extracted.get("account_number", ""))
    stored_account = normalize(stored.get("account_number", ""))
    
    if not extracted_account:
        errors.append("❌ Account number not found in cheque image")
    elif extracted_account != stored_account:
        errors.append(
            f"❌ Account number mismatch\n"
            f"   Expected: {stored['account_number']}\n"
            f"   Found: {extracted.get('account_number')}"
        )
    else:
        matched_fields.append("✅ Account number matched")
    
    extracted_ifsc = normalize(extracted.get("ifsc", ""))
    stored_ifsc = normalize(stored.get("ifsc", ""))
    
    if not extracted_ifsc:
        errors.append("❌ IFSC code not found in cheque image")
    elif extracted_ifsc != stored_ifsc:
        errors.append(
            f"❌ IFSC code mismatch\n"
            f"   Expected: {stored['ifsc']}\n"
            f"   Found: {extracted.get('ifsc')}"
        )
    else:
        matched_fields.append("✅ IFSC code matched")
    
    is_valid = len(errors) == 0
    
    return {
        "is_valid": is_valid,
        "reason": "\n".join(errors) if errors else "All details matched successfully",
        "matched_fields": matched_fields,
        "extracted_details": extracted,
        "errors": errors
    }


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