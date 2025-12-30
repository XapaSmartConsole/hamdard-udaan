from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from models import User, KYC
from typing import List

router = APIRouter(prefix="/api/kyc", tags=["KYC"])


# ============================================================
# ✅ COMPLETE KYC (OCR BASED – MAIN ENDPOINT)
# ============================================================
# ============================================================
# KYC SUMMARY (FOR DASHBOARD)
# ============================================================
@router.get("/summary")
def get_kyc_summary(db: Session = Depends(get_db)):
    """Get summary statistics of all KYC submissions"""
    
    total_users = db.query(User).count()
    
    # Count users with at least 3 documents (COMPLETED)
    completed_query = text("""
        SELECT COUNT(DISTINCT user_id) as count
        FROM kyc
        GROUP BY user_id
        HAVING COUNT(*) >= 3
    """)
    completed_result = db.execute(completed_query).scalar()
    completed = completed_result if completed_result else 0
    
    # Pending = total - completed
    pending = total_users - completed
    
    return {
        "total": total_users,
        "completed": completed,
        "pending": pending
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