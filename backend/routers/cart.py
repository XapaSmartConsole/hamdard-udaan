from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Cart, Wallet, Order, OrderItem
from datetime import datetime
import time
import re

router = APIRouter(prefix="/api", tags=["Cart"])


# ================= HELPER: EXTRACT BRAND FROM PRODUCT NAME =================
def extract_brand(product_name: str) -> str:
    """Extract brand name from product name (first word/brand identifier)"""
    # Common brand patterns
    brands = [
        'PORTRONICS', 'BAJAJ', 'Amkette', 'HP', 'JBL', 'BOAT', 'SanDisk', 'Havells',
        'PIGEON', 'ATLASWARE', 'ambrane', 'LOGITECH', 'NOISE', 'realme', 'Sony',
        'TIMEX', 'USHA', 'ZEBRONICS', 'Morphy Richards', 'Polycab', 'ARCADIO',
        'OnePlus', 'Redmi', 'POCO', 'Samsung', 'acer', 'GUESS', 'TVS', 'Yakuza',
        'Honda', 'Zomato', 'Shoppers Stop', 'Apollo', 'Healthians', 'Bikanervala',
        'McDonalds', 'Vaango', 'Bigbasket', 'Reliance', 'Zepto', 'Eazydiner',
        'Flipkart', 'Domino', 'Archies', 'Bata', 'Hush Puppies', 'Ferns N Petals',
        'PVR', 'Surat Diamonds', 'Timezone', 'LENSKART', 'Machaan', 'Mainland China',
        'Nykaa', 'Third Wave Coffee', 'Costa Coffee', 'Relaxo', 'BookMyShow',
        'Lifestyle', 'OLA', 'Uber', 'Westside', 'Amazon', 'KFC', 'Pizza Hut',
        'Behrouz', 'Birkenstock', 'Pantaloons', 'Marks & Spencer', 'Beer Cafe',
        'Safari', 'Cleartrip', 'Skechers', 'Woodland', 'FirstCry', 'Hamleys',
        'Decathlon', 'Lakme', 'Spencer', 'Vijay Sales', 'American Tourister',
        'Air India', 'Barbeque Nation', 'Blackberry', 'Fastrack', 'Makemytrip',
        'Wrangler', 'IRCTC', 'Welspun', 'WILDCRAFT', 'VIP', 'PC Jeweller',
        'Tanishq', 'Rangoli', 'Mia', 'Lenovo', 'ASUS', 'Green Sunny', 'Onix',
        'WONDERCHEF', 'My Bento', 'Prabha', 'Wonderchef', 'TUPPERWARE', 'Butterfly',
        'Milton', 'MYBENTO', 'SOWBAGHYA', 'BOROSIL', 'Berry', 'Kent', 'IMPEX',
        'Murugan', 'PRESTIGE', 'Crompton', 'KENSTAR', 'V GUARD', 'hindware',
        'LIFELONG', 'Orient', 'Maharaja Whiteline', 'AGARO', 'Whirlpool', 'LG',
        'Voltas', 'Carrier', 'Lloyd', 'Lifelong', 'Omron'
    ]
    
    for brand in brands:
        if product_name.upper().startswith(brand.upper()):
            return brand
    
    # Fallback: return first word
    return product_name.split()[0] if product_name else "Unknown"


# ================= GET PRODUCT ANALYTICS =================
@router.get("/products/analytics")
def get_product_analytics(category: str = None, db: Session = Depends(get_db)):
    """Get product redemption counts and analytics for filtering"""
    
    query = db.query(
        OrderItem.product_name,
        OrderItem.product_code,
        OrderItem.brand,
        func.sum(OrderItem.quantity).label('total_redeemed'),
        func.max(OrderItem.order.created_at).label('last_redeemed')
    ).join(Order)
    
    if category:
        query = query.filter(OrderItem.category == category)
    
    results = query.group_by(
        OrderItem.product_name,
        OrderItem.product_code,
        OrderItem.brand
    ).all()
    
    analytics = {}
    for row in results:
        analytics[row.product_name] = {
            'total_redeemed': row.total_redeemed,
            'product_code': row.product_code,
            'brand': row.brand,
            'last_redeemed': row.last_redeemed.isoformat() if row.last_redeemed else None
        }
    
    return analytics


# ================= GET CART =================
@router.get("/cart")
def get_cart(user_id: int, db: Session = Depends(get_db)):
    """Get all cart items for a user"""
    
    cart_items = db.query(Cart).filter(Cart.user_id == user_id).all()
    
    items = []
    total_points = 0
    
    for item in cart_items:
        items.append({
            "id": item.id,
            "product_name": item.product_name,
            "product_image": item.product_image,
            "points": item.points,
            "quantity": item.quantity,
            "category": item.category
        })
        total_points += item.points * item.quantity
    
    return {
        "items": items,
        "total_points": total_points,
        "count": len(items)
    }


# ================= ADD TO CART =================
@router.post("/cart/add")
def add_to_cart(
    user_id: int,
    product_name: str,
    points: int,
    product_image: str = "",
    category: str = "",
    product_code: str = "",
    quantity: int = 1,
    db: Session = Depends(get_db)
):
    """Add item to cart"""
    
    # Check if item already exists in cart
    existing = db.query(Cart).filter(
        Cart.user_id == user_id,
        Cart.product_name == product_name
    ).first()
    
    if existing:
        # Update quantity
        existing.quantity += quantity
        db.commit()
        db.refresh(existing)
        
        return {
            "success": True,
            "message": "Cart updated",
            "item": {
                "id": existing.id,
                "product_name": existing.product_name,
                "quantity": existing.quantity,
                "points": existing.points
            }
        }
    
    # Add new item
    cart_item = Cart(
        user_id=user_id,
        product_name=product_name,
        product_image=product_image,
        points=points,
        quantity=quantity,
        category=category
    )
    
    db.add(cart_item)
    db.commit()
    db.refresh(cart_item)
    
    return {
        "success": True,
        "message": "Item added to cart",
        "item": {
            "id": cart_item.id,
            "product_name": cart_item.product_name,
            "quantity": cart_item.quantity,
            "points": cart_item.points
        }
    }


# ================= REMOVE FROM CART =================
@router.delete("/cart/remove")
def remove_from_cart(user_id: int, cart_item_id: int, db: Session = Depends(get_db)):
    """Remove item from cart"""
    
    cart_item = db.query(Cart).filter(
        Cart.id == cart_item_id,
        Cart.user_id == user_id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    db.delete(cart_item)
    db.commit()
    
    return {"success": True, "message": "Item removed from cart"}


# ================= CLEAR CART =================
@router.delete("/cart/clear")
def clear_cart(user_id: int, db: Session = Depends(get_db)):
    """Clear all cart items"""
    
    db.query(Cart).filter(Cart.user_id == user_id).delete()
    db.commit()
    
    return {"success": True, "message": "Cart cleared"}


# ================= CHECKOUT =================
@router.post("/cart/checkout")
def checkout_cart(
    user_id: int,
    delivery_address: str,
    mobile: str,
    db: Session = Depends(get_db)
):
    """Checkout cart and create order"""
    
    print(f"\n{'='*50}")
    print(f"🛒 CHECKOUT STARTED")
    print(f"User ID: {user_id}")
    print(f"{'='*50}\n")
    
    # Get cart items
    cart_items = db.query(Cart).filter(Cart.user_id == user_id).all()
    
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Calculate total points
    total_points = sum(item.points * item.quantity for item in cart_items)
    print(f"💰 Total points to redeem: {total_points}")
    
    # Get wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    
    if not wallet:
        print(f"❌ ERROR: Wallet not found for user_id: {user_id}")
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    print(f"💳 BEFORE - Wallet balance: {wallet.points}")
    print(f"📊 BEFORE - Total redeemed: {wallet.redeemed}")
    
    if wallet.points < total_points:
        print(f"❌ ERROR: Insufficient points")
        raise HTTPException(status_code=400, detail="Insufficient points")
    
    # ✅ DEDUCT POINTS FROM WALLET
    wallet.points = wallet.points - total_points
    wallet.redeemed = wallet.redeemed + total_points
    
    print(f"\n🔄 UPDATING WALLET...")
    print(f"   New balance: {wallet.points}")
    print(f"   New redeemed: {wallet.redeemed}")
    
    # Generate unique order ID
    order_id = f"ORD{int(time.time() * 1000) % 100000000}"
    
    # Create order
    order = Order(
        user_id=user_id,
        order_id=order_id,
        total_points=total_points,
        delivery_address=delivery_address,
        mobile=mobile,
        status="completed",
        transaction_type="PRODUCT",
        created_at=datetime.now()
    )
    
    db.add(order)
    print(f"📦 Order created: {order_id}")
    
    # Create order items with brand extraction
    for cart_item in cart_items:
        brand = extract_brand(cart_item.product_name)
        
        order_item = OrderItem(
            order_id=order_id,
            product_name=cart_item.product_name,
            product_image=cart_item.product_image,
            points=cart_item.points,
            quantity=cart_item.quantity,
            category=cart_item.category,
            product_code=getattr(cart_item, 'product_code', ''),
            brand=brand  # ✅ NEW: Extract and save brand
        )
        db.add(order_item)
    
    print(f"📝 Added {len(cart_items)} items to order")
    
    # Clear cart
    db.query(Cart).filter(Cart.user_id == user_id).delete()
    print(f"🗑️  Cart cleared")
    
    # ✅ COMMIT ALL CHANGES
    print(f"\n💾 COMMITTING TO DATABASE...")
    try:
        db.commit()
        print(f"✅ COMMIT SUCCESSFUL")
    except Exception as e:
        print(f"❌ COMMIT FAILED: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Refresh to verify
    db.refresh(wallet)
    
    print(f"\n💳 AFTER COMMIT - Wallet balance: {wallet.points}")
    print(f"📊 AFTER COMMIT - Total redeemed: {wallet.redeemed}")
    print(f"\n{'='*50}")
    print(f"✅ CHECKOUT COMPLETE")
    print(f"{'='*50}\n")
    
    return {
        "success": True,
        "message": "Order placed successfully",
        "order_id": order_id,
        "total_points": total_points,
        "remaining_points": wallet.points
    }