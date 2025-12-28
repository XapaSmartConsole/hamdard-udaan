from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Order, OrderItem, Cart
import time

router = APIRouter(prefix="/api/orders", tags=["Orders"])


# ================= CREATE ORDER FROM CART =================
@router.post("/create")
def create_order(
    user_id: int,
    total_points: int,
    db: Session = Depends(get_db)
):
    """Create order from cart items"""
    
    # Generate unique order ID
    order_id = f"ORD{int(time.time() * 1000) % 100000000}"
    
    # Get cart items
    cart_items = db.query(Cart).filter(Cart.user_id == user_id).all()
    
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # ✅ Create order with PRODUCT transaction type
    new_order = Order(
        user_id=user_id,
        order_id=order_id,
        total_points=total_points,
        status="completed",
        transaction_type="PRODUCT"  # ✅ Mark as product redemption
    )
    db.add(new_order)
    db.flush()
    
    # Create order items from cart
    for item in cart_items:
        order_item = OrderItem(
            order_id=order_id,
            product_name=item.product_name,
            points=item.points,
            product_image=item.product_image,
            category=item.category,
            quantity=item.quantity
        )
        db.add(order_item)
    
    # Clear cart after order creation
    db.query(Cart).filter(Cart.user_id == user_id).delete()
    
    db.commit()
    
    return {
        "success": True,
        "order_id": order_id,
        "message": "Order placed successfully"
    }


# ================= GET USER ORDER HISTORY =================
@router.get("/user")
def get_user_orders(user_id: int, db: Session = Depends(get_db)):
    """Get order history for a user - sorted by newest first"""
    
    orders = db.query(Order).filter(
        Order.user_id == user_id
    ).order_by(Order.created_at.desc()).all()
    
    result = []
    for order in orders:
        # Get items for this order
        items = db.query(OrderItem).filter(
            OrderItem.order_id == order.order_id
        ).all()
        
        # ✅ Determine transaction type and label
        transaction_type = order.transaction_type or "PRODUCT"
        
        if transaction_type == "BANK_TRANSFER":
            transaction_label = "Bank Transfer"
        elif transaction_type == "CASHOUT":
            transaction_label = "Points Redemption"
        else:
            transaction_label = "Product Redemption"
        
        # ✅ Include transaction_type in response
        result.append({
            "id": order.order_id,
            "date": order.created_at.isoformat() if order.created_at else None,
            "total_points": order.total_points,
            "status": order.status,
            "transaction_type": transaction_type,  # ✅ BANK_TRANSFER, CASHOUT, or PRODUCT
            "transaction_label": transaction_label,  # ✅ Human-readable label
            "items": [
                {
                    "name": item.product_name,
                    "points": item.points,
                    "quantity": item.quantity,
                    "image": item.product_image,
                    "category": item.category
                }
                for item in items
            ]
        })
    
    return result


# ================= GET ORDER DETAILS =================
@router.get("/{order_id}")
def get_order_details(order_id: str, db: Session = Depends(get_db)):
    """Get details of a specific order"""
    
    order = db.query(Order).filter(Order.order_id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get items
    items = db.query(OrderItem).filter(
        OrderItem.order_id == order_id
    ).all()
    
    return {
        "order_id": order.order_id,
        "user_id": order.user_id,
        "total_points": order.total_points,
        "status": order.status,
        "transaction_type": order.transaction_type,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {
                "name": item.product_name,
                "points": item.points,
                "quantity": item.quantity,
                "image": item.product_image,
                "category": item.category
            }
            for item in items
        ]
    }