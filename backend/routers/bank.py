from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from backend.database import get_db      # ✅ FIXED
from backend.models import Bank
import openai
import os
import json
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

router = APIRouter(prefix="/api", tags=["Bank"])

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY", "your-openai-api-key-here")

# ============================================================
# ADD / UPDATE BANK DETAILS
# ============================================================
@router.post("/bank/add")
def add_or_update_bank(
    user_id: int = Form(...),
    account_holder_name: str = Form(...),
    bank_name: str = Form(...),
    account_number: str = Form(...),
    ifsc: str = Form(...),
    cheque_image: str = Form(...),  # Base64 string
    db: Session = Depends(get_db)
):
    # Check if bank details already exist
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()

    if bank:
        # Update existing
        bank.account_holder_name = account_holder_name
        bank.bank_name = bank_name
        bank.account_number = account_number
        bank.ifsc = ifsc
        bank.cheque_image = cheque_image
        # Reset validation status on update
        bank.is_validated = False
        bank.validation_status = "PENDING"
    else:
        # Create new
        bank = Bank(
            user_id=user_id,
            account_holder_name=account_holder_name,
            bank_name=bank_name,
            account_number=account_number,
            ifsc=ifsc,
            cheque_image=cheque_image,
            is_validated=False,
            validation_status="PENDING"
        )
        db.add(bank)

    db.commit()

    return {
        "success": True,
        "message": "Bank details saved successfully"
    }


# ============================================================
# GET BANK DETAILS
# ============================================================
@router.get("/bank")
def get_bank_details(
    user_id: int,
    db: Session = Depends(get_db)
):
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()

    if not bank:
        raise HTTPException(status_code=404, detail="Bank details not found")

    return {
        "user_id": bank.user_id,
        "account_holder_name": bank.account_holder_name,
        "bank_name": bank.bank_name,
        "account_number": bank.account_number,
        "ifsc": bank.ifsc,
        "cheque_image": bank.cheque_image,
        "is_validated": bank.is_validated if hasattr(bank, 'is_validated') else False,
        "validation_status": bank.validation_status if hasattr(bank, 'validation_status') else "PENDING"
    }


# ============================================================
# VALIDATE BANK ACCOUNT (AI-POWERED)
# ============================================================
@router.post("/bank/validate")
async def validate_bank_account(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Automatically validate bank account by extracting details from cheque image
    using OpenAI Vision API and comparing with stored details
    """
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()
    
    if not bank:
        raise HTTPException(status_code=404, detail="Bank details not found")
    
    # Check if already validated
    if hasattr(bank, 'is_validated') and bank.is_validated:
        return {
            "message": "Bank account already validated",
            "is_validated": True,
            "validation_status": "VALIDATED"
        }
    
    try:
        # Extract base64 image data
        if bank.cheque_image.startswith("data:image"):
            base64_image = bank.cheque_image.split(",")[1]
        else:
            base64_image = bank.cheque_image
        
        # Call OpenAI Vision API to extract bank details from cheque
        extracted_details = await extract_bank_details_from_cheque(base64_image)
        
        # Compare extracted details with stored details
        validation_result = validate_extracted_details(
            extracted_details,
            {
                "account_holder_name": bank.account_holder_name,
                "account_number": bank.account_number,
                "ifsc": bank.ifsc
            }
        )
        
        if validation_result["is_valid"]:
            # Update validation status
            if hasattr(bank, 'is_validated'):
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
            # Validation failed
            if hasattr(bank, 'is_validated'):
                bank.is_validated = False
                bank.validation_status = "FAILED"
            db.commit()
            
            raise HTTPException(
                status_code=400,
                detail=f"Validation failed: {validation_result['reason']}"
            )
    
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
# HELPER: EXTRACT BANK DETAILS FROM CHEQUE USING OPENAI
# ============================================================
async def extract_bank_details_from_cheque(base64_image: str) -> dict:
    """
    Use OpenAI Vision API to extract bank details from cancelled cheque image
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",  # or "gpt-4-vision-preview"
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
            temperature=0  # More deterministic output
        )
        
        # Parse the response
        content = response.choices[0].message.content.strip()
        
        print(f"🤖 OpenAI Response: {content}")
        
        # Extract JSON from the response
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
# HELPER: VALIDATE EXTRACTED DETAILS AGAINST STORED DETAILS
# ============================================================
def validate_extracted_details(extracted: dict, stored: dict) -> dict:
    """
    Compare extracted details with stored details
    Returns validation result with specific error messages
    """
    errors = []
    matched_fields = []
    
    # Normalize strings for comparison (remove spaces, special chars, convert to uppercase)
    def normalize(s):
        if not s or s == "NOT_FOUND":
            return None
        # Remove all non-alphanumeric characters and convert to uppercase
        return re.sub(r'[^A-Z0-9]', '', str(s).upper())
    
    # ========== VALIDATE ACCOUNT HOLDER NAME ==========
    extracted_name = normalize(extracted.get("account_holder_name", ""))
    stored_name = normalize(stored.get("account_holder_name", ""))
    
    if not extracted_name:
        errors.append("❌ Account holder name not found in cheque image")
    else:
        # Calculate similarity (allow for minor OCR errors)
        similarity = calculate_similarity(extracted_name, stored_name)
        
        if similarity >= 0.75:  # 75% match threshold
            matched_fields.append("✅ Account holder name matched")
        else:
            errors.append(
                f"❌ Account holder name mismatch\n"
                f"   Expected: {stored['account_holder_name']}\n"
                f"   Found in cheque: {extracted.get('account_holder_name')}\n"
                f"   Similarity: {int(similarity * 100)}%"
            )
    
    # ========== VALIDATE ACCOUNT NUMBER ==========
    extracted_account = normalize(extracted.get("account_number", ""))
    stored_account = normalize(stored.get("account_number", ""))
    
    if not extracted_account:
        errors.append("❌ Account number not found in cheque image")
    elif extracted_account != stored_account:
        errors.append(
            f"❌ Account number mismatch\n"
            f"   Expected: {stored['account_number']}\n"
            f"   Found in cheque: {extracted.get('account_number')}"
        )
    else:
        matched_fields.append("✅ Account number matched")
    
    # ========== VALIDATE IFSC CODE ==========
    extracted_ifsc = normalize(extracted.get("ifsc", ""))
    stored_ifsc = normalize(stored.get("ifsc", ""))
    
    if not extracted_ifsc:
        errors.append("❌ IFSC code not found in cheque image")
    elif extracted_ifsc != stored_ifsc:
        errors.append(
            f"❌ IFSC code mismatch\n"
            f"   Expected: {stored['ifsc']}\n"
            f"   Found in cheque: {extracted.get('ifsc')}"
        )
    else:
        matched_fields.append("✅ IFSC code matched")
    
    # Determine if validation passed
    is_valid = len(errors) == 0
    
    return {
        "is_valid": is_valid,
        "reason": "\n".join(errors) if errors else "All details matched successfully",
        "matched_fields": matched_fields,
        "extracted_details": extracted,
        "errors": errors
    }


# ============================================================
# HELPER: CALCULATE STRING SIMILARITY (LEVENSHTEIN DISTANCE)
# ============================================================
def calculate_similarity(s1: str, s2: str) -> float:
    """
    Calculate similarity between two strings using Levenshtein distance
    Returns a float between 0 (completely different) and 1 (identical)
    """
    if not s1 or not s2:
        return 0.0
    
    if s1 == s2:
        return 1.0
    
    # Ensure s1 is shorter or equal length
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    
    len1, len2 = len(s1), len(s2)
    
    # Initialize distance matrix
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
    
    # Calculate similarity as 1 - (distance / max_length)
    distance = current_row[len1]
    max_len = max(len(s1), len(s2))
    
    similarity = 1 - (distance / max_len) if max_len > 0 else 0.0
    
    return similarity