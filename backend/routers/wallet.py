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

    balance = wallet.points

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
    
    orders = db.query(Order).filter(
        Order.user_id == user_id
    ).order_by(Order.created_at.desc()).limit(limit).all()
    
    transactions = []
    
    for order in orders:
        items = db.query(OrderItem).filter(
            OrderItem.order_id == order.order_id
        ).all()
        
        for item in items:
            is_voucher = item.category and "voucher" in item.category.lower()
            
            if is_voucher:
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

    new_balance = wallet.points

    return {
        "success": True,
        "message": f"Successfully redeemed {points} points",
        "order_id": order_id,
        "points": wallet.points,
        "redeemed": wallet.redeemed,
        "new_balance": new_balance
    }


# ================= BANK TRANSFER WITH 15% TDS =================
@router.post("/wallet/bank-transfer")
def bank_transfer(
    user_id: int,
    points: int,
    db: Session = Depends(get_db)
):
    """
    Transfer points to bank account with 15% TDS deduction
    1 Point = ₹1
    TDS = 15%
    Net Amount = Gross Amount - (Gross Amount × 15%)
    """
    
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
    
    # Check if bank/UPI details exist
    bank = db.query(Bank).filter(Bank.user_id == user_id).first()
    
    if not bank:
        raise HTTPException(
            status_code=404, 
            detail="Payment details not found. Please add bank or UPI details first."
        )
    
    # Get payment method
    payment_method = getattr(bank, 'payment_method', 'BANK')
    
    # ============ CALCULATE 15% TDS ============
    TDS_PERCENTAGE = 15.0
    gross_amount = points  # 1 point = ₹1
    tds_amount = int((gross_amount * TDS_PERCENTAGE) / 100)
    net_amount = gross_amount - tds_amount
    
    # Deduct points from wallet
    wallet.points -= points
    wallet.redeemed += points
    
    # Create transaction ID
    transaction_id = f"TXN{int(time.time() * 1000) % 100000000}"
    
    # Get payment identifier for description
    if payment_method == "UPI":
        payment_identifier = getattr(bank, 'upi_id', 'UPI Account')
        transaction_type = "UPI_TRANSFER"
    else:
        account_number = getattr(bank, 'account_number', 'XXXX')
        bank_name = getattr(bank, 'bank_name', 'Bank')
        payment_identifier = f"{bank_name} A/C ****{account_number[-4:]}" if account_number else "Bank Account"
        transaction_type = "BANK_TRANSFER"
    
    # Create order entry for bank transfer
    bank_transfer_order = Order(
        user_id=user_id,
        order_id=transaction_id,
        total_points=points,
        status="completed",
        transaction_type=transaction_type
    )
    db.add(bank_transfer_order)
    
    # Create transaction record with TDS details
    try:
        transaction = Transaction(
            user_id=user_id,
            transaction_type=transaction_type,
            points=points,
            amount=gross_amount,
            tds_percentage=int(TDS_PERCENTAGE),
            tds_amount=tds_amount,
            net_amount=net_amount,
            description=f"Transfer to {payment_identifier} | Gross: ₹{gross_amount} | TDS (15%): ₹{tds_amount} | Net: ₹{net_amount}",
            status="COMPLETED"
        )
        db.add(transaction)
    except Exception as e:
        print(f"Transaction record error: {e}")
    
    db.commit()
    db.refresh(wallet)
    
    return {
        "success": True,
        "message": f"Transfer successful",
        "transaction_details": {
            "transaction_id": transaction_id,
            "payment_method": payment_method,
            "payment_to": payment_identifier,
            "points_deducted": points,
            "gross_amount": gross_amount,
            "tds_percentage": 15,
            "tds_amount": tds_amount,
            "net_amount": net_amount,
            "remaining_points": wallet.points
        }
    }


# ================= ADD MONEY (DEMO) =================
@router.post("/wallet/add-money")
def add_money(user_id: int, amount: float, type: str = "DEMO_CREDIT", db: Session = Depends(get_db)):
    """Demo endpoint to add money to wallet"""
    
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    
    if not wallet:
        wallet = Wallet(
            user_id=user_id,
            points=6000,
            redeemed=0
        )
        db.add(wallet)
    
    points_to_add = int(amount)
    wallet.points += points_to_add
    
    db.commit()
    db.refresh(wallet)
    
    new_balance = wallet.points
    
    return {
        "success": True,
        "message": f"Added ₹{amount} to wallet",
        "points_added": points_to_add,
        "new_balance": new_balance,
        "total_points": wallet.points
    }