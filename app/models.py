from flask_login import UserMixin
from . import db
from datetime import datetime

# =======================
# User Model (Unified)
# =======================
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    birthdate = db.Column(db.String(20), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    address = db.Column(db.String(200), nullable=True)
    contact = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50))  # e.g. "Barber", "Receptionist"
    is_admin = db.Column(db.Boolean, default=False)

    # Relationships
    bookings = db.relationship(
        'Booking',
        back_populates='user',
        foreign_keys='Booking.user_id',
        lazy=True
    )
    assigned_bookings = db.relationship(
        'Booking',
        back_populates='barber',
        foreign_keys='Booking.barber_id',
        lazy=True
    )

    def __repr__(self):
        return f'<User {self.full_name}>'


# =======================
# Booking Model
# =======================
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Client
    service = db.Column(db.String(100))
    date = db.Column(db.String(20))
    time = db.Column(db.String(20))
    order_code = db.Column(db.String(10), unique=True)
    status = db.Column(db.String(20), default='pending')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    payment_status = db.Column(db.String(20), default='unpaid')
    price = db.Column(db.Float, nullable=True) 
    barber_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Relationships
    user = db.relationship(
        'User',
        back_populates='bookings',
        foreign_keys=[user_id]
    )
    barber = db.relationship(
        'User',
        back_populates='assigned_bookings',
        foreign_keys=[barber_id]
    )

    def __repr__(self):
        return f'<Booking {self.order_code} - {self.service}>'


# =======================
# Product Model
# =======================
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(200))  # Path to image file

    def __repr__(self):
        return f'<Product {self.name}>'


# =======================
# Order Model
# =======================
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(10), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='orders')
    items = db.relationship('OrderItem', backref='order', lazy=True)

    def __repr__(self):
        return f'<Order {self.order_code}>'


# =======================
# OrderItem Model
# =======================
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    product = db.relationship('Product')

    def __repr__(self):
        return f'<OrderItem {self.product.name} x {self.quantity}>'


# =======================
# Service Model
# =======================
class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(120))  # Path to uploaded image

    def __repr__(self):
        return f'<Service {self.name}>'

# =======================
# Settings Model
# =======================
class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(100), nullable=False)

