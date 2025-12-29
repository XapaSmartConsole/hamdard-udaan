from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database import get_db      # ✅ FIXED
from backend.models import User, KYC
from typing import List

router = APIRouter(prefix="/api/kyc", tags=["KYC"])


# ============================================================
# ✅ COMPLETE KYC (OCR BASED – MAIN ENDPOINT)
# ============================================================
@router.post("/complete")
def complete_kyc(
    user_id: int = Form(...),
    document_type: str = Form(...),
    document_number: str = Form(...),
    db: Session = Depends(get_db)
):
    # Validate user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if this document type already exists for user
    existing_kyc = db.query(KYC).filter(
        KYC.user_id == user_id,
        KYC.document_type == document_type
    ).first()

    if existing_kyc:
        # Update existing document
        existing_kyc.document_number = document_number
        existing_kyc.status = "COMPLETED"
    else:
        # Create new KYC document record
        kyc = KYC(
            user_id=user_id,
            document_type=document_type,
            document_number=document_number,
            status="COMPLETED"
        )
        db.add(kyc)

    db.commit()

    return {
        "status": "success",
        "message": f"{document_type} document submitted successfully"
    }


# ============================================================
# GET ALL SUBMITTED DOCUMENTS FOR A USER
# ============================================================
@router.get("/documents")  # This will be /api/kyc/documents
def get_user_documents(user_id: int, db: Session = Depends(get_db)):
    """Get all submitted KYC documents for a user"""
    
    # Validate user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all KYC documents for this user
    documents = db.query(KYC).filter(KYC.user_id == user_id).all()
    
    # Return empty array if no documents (not error)
    if not documents:
        return []
    
    return [
        {
            "document_type": doc.document_type,
            "document_number": doc.document_number,
            "status": doc.status,
            "submitted_at": doc.created_at.isoformat() if doc.created_at else None
        }
        for doc in documents
    ]


# ============================================================
# USER KYC DETAILS (FOR DASHBOARD / PROFILE)
# ============================================================
@router.get("/me")
def get_my_kyc(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all KYC documents
    kyc_documents = db.query(KYC).filter(KYC.user_id == user_id).all()
    
    # Determine overall KYC status
    if not kyc_documents:
        overall_status = "PENDING"
    elif len(kyc_documents) >= 3:  # Address, PAN, GST all submitted
        overall_status = "COMPLETED"
    else:
        overall_status = "PARTIAL"

    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "phone": user.phone,
        "kyc_status": overall_status,
        "documents_submitted": len(kyc_documents),
        "documents": [
            {
                "type": doc.document_type,
                "number": doc.document_number,
                "status": doc.status
            }
            for doc in kyc_documents
        ]
    }


# ============================================================
# KYC STATUS CHECK (BANK / WALLET / GUARDS)
# ============================================================
@router.get("/status")
def get_kyc_status(user_id: int, db: Session = Depends(get_db)):
    kyc_documents = db.query(KYC).filter(KYC.user_id == user_id).all()
    
    if not kyc_documents:
        status = "PENDING"
    elif len(kyc_documents) >= 3:
        status = "COMPLETED"
    else:
        status = "PARTIAL"

    return {
        "kyc_status": status,
        "documents_count": len(kyc_documents)
    }


# ============================================================
# DELETE A SPECIFIC DOCUMENT (OPTIONAL)
# ============================================================
@router.delete("/document/{document_type}")
def delete_document(
    user_id: int,
    document_type: str,
    db: Session = Depends(get_db)
):
    """Delete a specific KYC document"""
    
    doc = db.query(KYC).filter(
        KYC.user_id == user_id,
        KYC.document_type == document_type
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    db.delete(doc)
    db.commit()
    
    return {
        "status": "success",
        "message": f"{document_type} document deleted successfully"
    }


# ============================================================
# GET SPECIFIC DOCUMENT TYPE
# ============================================================
@router.get("/document/{document_type}")
def get_specific_document(
    user_id: int,
    document_type: str,
    db: Session = Depends(get_db)
):
    """Get a specific document type for a user"""
    
    doc = db.query(KYC).filter(
        KYC.user_id == user_id,
        KYC.document_type == document_type
    ).first()
    
    if not doc:
        return {
            "found": False,
            "message": f"{document_type} not submitted yet"
        }
    
    return {
        "found": True,
        "document_type": doc.document_type,
        "document_number": doc.document_number,
        "status": doc.status,
        "submitted_at": doc.created_at.isoformat() if doc.created_at else None
    }


# ============================================================
# ADMIN – ALL USERS KYC LIST
# ============================================================
@router.get("/admin/users")
def admin_kyc_users(db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT 
            u.id,
            u.full_name,
            u.phone,
            COUNT(k.id) as documents_submitted,
            CASE 
                WHEN COUNT(k.id) = 0 THEN 'PENDING'
                WHEN COUNT(k.id) >= 3 THEN 'COMPLETED'
                ELSE 'PARTIAL'
            END as kyc_status
        FROM users u
        LEFT JOIN kyc k ON u.id = k.user_id
        GROUP BY u.id, u.full_name, u.phone
        ORDER BY u.id DESC
    """)).mappings().all()

    return list(result)