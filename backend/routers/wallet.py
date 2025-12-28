from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Wallet, Order, OrderItem, Transaction, Bank
import time
from datetime import datetime

router = APIRouter(prefix="/api", tags=["Wallet"])


# ================= WALLET BALANCE (PRIMARY ENDPOINT) =================
@router.get("/wallet/balance")
def wallet_balance(user_id: int, db: Session = Depends(get_db)):
    """Get wallet balance - creates wallet if doesn't exist"""
    
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()

    # Auto-create wallet with default points
    if not wallet:
        wallet = Wallet(
            user_id=user_id,
            points=6000,
            redeemed=0
        )
        db.add(wallet)
        db.commit()
        db.refresh(wallet)

    # ✅ FIXED: 1 Point = ₹1 (was calculating wrong)
    balance = wallet.points  # Direct 1:1 conversion

    return {
        "points": wallet.points,
        "redeemed": wallet.redeemed,
        "balance": balance
    }


# ================= WALLET SUMMARY (ALIAS) =================
@router.get("/wallet/summary")
def wallet_summary(user_id: int, db: Session = Depends(get_db)):
    """Alias for wallet balance"""
    return wallet_balance(user_id, db)


# ================= GET VOUCHER TRANSACTIONS =================
@router.get("/wallet/transactions")
def get_wallet_transactions(user_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """Get voucher redemption history (eGV wallet transactions)"""
    
    # Get all orders for this user
    orders = db.query(Order).filter(
        Order.user_id == user_id
    ).order_by(Order.created_at.desc()).limit(limit).all()
    
    transactions = []
    
    for order in orders:
        # Get order items (products/vouchers)
        items = db.query(OrderItem).filter(
            OrderItem.order_id == order.order_id
        ).all()
        
        # For voucher items, generate voucher code and PIN
        for item in items:
            # Check if this is a voucher (based on category)
            is_voucher = item.category and "voucher" in item.category.lower()
            
            if is_voucher:
                # Generate voucher code and PIN
                voucher_code = f"VCH{order.order_id[-6:]}"
                voucher_pin = f"{hash(order.order_id) % 10000:04d}"
                
                transactions.append({
                    "transaction_id": order.order_id,
                    "order_id": order.order_id,
                    "product_name": item.product_name,
                    "voucher_code": voucher_code,
                    "pin": voucher_pin,
                    "amount": item.points,
                    "type": "Voucher Redemption",
                    "status": order.status.upper(),
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "date_of_redemption": order.created_at.strftime("%d %b %Y") if order.created_at else None
                })
            else:
                # Regular product redemption
                transactions.append({
                    "transaction_id": order.order_id,
                    "order_id": order.order_id,
                    "product_name": item.product_name,
                    "voucher_code": None,
                    "pin": None,
                    "amount": item.points,
                    "type": "Product Redemption",
                    "status": order.status.upper(),
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "date_of_redemption": order.created_at.strftime("%d %b %Y") if order.created_at else None
                })
    
    return transactions


# ================= REDEEM POINTS (CASHOUT) =================
@router.post("/wallet/redeem-points")
def redeem_points(user_id: int, points: int, db: Session = Depends(get_db)):
    """Redeem points from wallet - creates order entry for transaction history"""
    
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    if points <= 0:
        raise HTTPException(status_code=400, detail="Invalid points amount")

    if wallet.points < points:
        raise HTTPException(status_code=400, detail="Insufficient points")

    # Deduct points from wallet
    wallet.points -= points
    wallet.redeemed += points

    # CREATE ORDER ENTRY FOR CASHOUT TRANSACTION
    order_id = f"CSH{int(time.time() * 1000) % 100000000}"
    
    cashout_order = Order(
        user_id=user_id,
        order_id=order_id,
        total_points=points,
        status="completed",
        transaction_type="CASHOUT"
    )
    db.add(cashout_order)

    db.commit()
    db.refresh(wallet)

    # ✅ FIXED: Calculate new balance (1 Point = ₹1)
    new_balance = wallet.points  # Direct 1:1 conversion

    return {
        "success": True,
        "message": f"Successfully redeemed {points} points",
        "order_id": order_id,
        "points": wallet.points,
        "redeemed": wallet.redeemed,
        "new_balance": new_balance
    }


# ================= BANK TRANSFER =================
@router.post("/wallet/bank-transfer")
def bank_transfer(
    user_id: int,
    points: int,
    db: Session = Depends(get_db)
):
    """Transfer points to bank account (1 Point = ₹1)"""
    
    # Get wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Validate points
    if points <= 0:
        raise HTTPException(status_code=400, detail="Invalid transfer amount")
    
    if wallet.points < points:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient points. Available: {wallet.points}, Required: {points}"
        )
    
    # Check if bank details exist
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()
    
    if not bank:
        raise HTTPException(
            status_code=404, 
            detail="Bank details not found. Please add bank details first."
        )
    
    # ✅ FIXED: 1 Point = ₹1 (Direct conversion, no division or multiplication)
    amount = points  # Simple 1:1 conversion
    
    # Deduct points from wallet
    wallet.points -= points
    wallet.redeemed += points
    
    # Create transaction record
    transaction_id = f"TXN{int(time.time() * 1000) % 100000000}"
    
    # Create order entry for bank transfer
    bank_transfer_order = Order(
        user_id=user_id,
        order_id=transaction_id,
        total_points=points,
        status="completed",
        transaction_type="BANK_TRANSFER"
    )
    db.add(bank_transfer_order)
    
    # Create transaction record
    try:
        transaction = Transaction(
            user_id=user_id,
            transaction_type="BANK_TRANSFER",
            points=-points,
            amount=amount,
            description=f"Bank transfer of ₹{amount} to {bank.bank_name} A/C ****{bank.account_number[-4:]}"
        )
        db.add(transaction)
    except Exception as e:
        print(f"Transaction record error: {e}")
    
    db.commit()
    db.refresh(wallet)
    
    return {
        "success": True,
        "message": f"₹{amount} transferred successfully to your {bank.bank_name} account",
        "transaction_id": transaction_id,
        "points_deducted": points,
        "amount_transferred": amount,
        "remaining_points": wallet.points,
        "bank_details": {
            "bank_name": bank.bank_name,
            "account_number": f"****{bank.account_number[-4:]}",
            "account_holder_name": bank.account_holder_name
        }
    }


# ================= ADD MONEY (DEMO) =================
@router.post("/wallet/add-money")
def add_money(user_id: int, amount: float, type: str = "DEMO_CREDIT", db: Session = Depends(get_db)):
    """Demo endpoint to add money to wallet"""
    
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    
    if not wallet:
        # Create wallet if doesn't exist
        wallet = Wallet(
            user_id=user_id,
            points=6000,
            redeemed=0
        )
        db.add(wallet)
    
    # ✅ FIXED: Convert amount to points (1 Point = ₹1)
    points_to_add = int(amount)  # Direct 1:1 conversion
    
    wallet.points += points_to_add
    
    db.commit()
    db.refresh(wallet)
    
    # Calculate new balance
    new_balance = wallet.points  # Direct 1:1 conversion
    
    return {
        "success": True,
        "message": f"Added ₹{amount} to wallet",
        "points_added": points_to_add,
        "new_balance": new_balance,
        "total_points": wallet.points
    }