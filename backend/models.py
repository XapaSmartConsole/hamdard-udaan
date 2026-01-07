from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from datetime import datetime
from sqlalchemy.dialects.mysql import LONGTEXT




# =======================
# USER
# =======================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100))
    phone = Column(String(15), unique=True, index=True)
    email = Column(String(100), nullable=True)
    otp = Column(String(6))
    otp_verified = Column(Boolean, default=False)
    
    # Profile fields
    profile_picture = Column(Text(length=2**32-1), nullable=True)
    ham_code = Column(String(20), unique=True, nullable=True)
    be_name = Column(String(100), nullable=True)
    outlet_name = Column(String(100), nullable=True)  # ✅ NEW
    
    # Business fields
    member_type = Column(String(50), nullable=True)
    slab = Column(String(50), nullable=True)
    distributor_name = Column(String(100), nullable=True)
    target = Column(Integer, nullable=True)
    
    # Location fields
    region = Column(String(50), nullable=True)
    state = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    pincode = Column(String(10), nullable=True)

    # Relationships
    cart_items = relationship("Cart", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")


# =======================
# KYC
# =======================
class KYC(Base):
    __tablename__ = "kyc"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    document_type = Column(String(50), nullable=False)
    document_number = Column(String(100), nullable=False)
    status = Column(String(20), default="COMPLETED")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'document_type', name='unique_user_document'),
    )


# =======================
# BANK
# =======================
class Bank(Base):
    __tablename__ = "bank_details"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    payment_method = Column(String(10), default="BANK")

    # Bank fields
    account_holder_name = Column(String(255))
    bank_name = Column(String(255))
    account_number = Column(String(50))
    ifsc = Column(String(11))
    cheque_image = Column(LONGTEXT)

    # UPI fields
    upi_id = Column(String(255))
    upi_qr_code = Column(LONGTEXT)

    # Validation
    is_validated = Column(Boolean, default=False)
    validation_status = Column(String(20), default="PENDING")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)




# =======================
# WALLET
# =======================
class Wallet(Base):
    __tablename__ = "wallet"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    points = Column(Integer, default=6000)
    redeemed = Column(Integer, default=0)


# =======================
# TRANSACTION
# =======================
# =======================
# TRANSACTION
# =======================
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    transaction_type = Column(String(50), nullable=False)
    points = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=True)
    
    # TDS fields (15% TDS)
    tds_percentage = Column(Integer, default=15)
    tds_amount = Column(Integer, default=0)
    net_amount = Column(Integer, default=0)
    
    description = Column(Text, nullable=True)
    status = Column(String(20), default="COMPLETED")
    created_at = Column(DateTime, default=lambda: datetime.now())
    
    user = relationship("User")


# =======================
# CART
# =======================

class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_name = Column(String(255))
    product_image = Column(String(500))
    points = Column(Integer)
    quantity = Column(Integer, default=1)
    category = Column(String(100))
    description = Column(Text, nullable=True)  # ✅ ADD THIS LINE
    created_at = Column(DateTime, default=lambda: datetime.now())

    user = relationship("User", back_populates="cart_items")


# =======================
# ORDER
# =======================
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_id = Column(String(50), unique=True, nullable=False, index=True)
    total_points = Column(Integer, nullable=False)
    delivery_address = Column(Text, nullable=True)
    mobile = Column(String(20), nullable=True)
    status = Column(String(50), default="completed")
    transaction_type = Column(String(20), default="PRODUCT")
    created_at = Column(DateTime, default=lambda: datetime.now())

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


# =======================
# ORDER ITEM
# =======================
class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), ForeignKey("orders.order_id"), nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    product_image = Column(Text, nullable=True)
    points = Column(Integer, nullable=False)
    quantity = Column(Integer, default=1)
    category = Column(String(100), nullable=True)

    order = relationship("Order", back_populates="items")