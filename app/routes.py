from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date
from . import db, login_manager
from .models import Service, User, Booking, Product, Order, OrderItem
import os, random, string, barcode
import qrcode
import io
import base64
from flask import render_template
from sqlalchemy import func, cast, Date
from flask import json, request
import pandas as pd
from io import BytesIO
from flask import send_file
from pytz import timezone, utc

main = Blueprint('main', __name__)

PRODUCT_UPLOAD_FOLDER = 'app/static/uploads/products'
SERVICE_UPLOAD_FOLDER = 'app/static/uploads/services'
BARCODE_FOLDER = 'app/static/barcodes'
QR_FOLDER = os.path.join('app', 'static', 'qr_codes')



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# === Home ===
@main.route('/')
@login_required
def base():
    products = Product.query.all()
    services = Service.query.all()  # ✅ Fetch services here
    return render_template('base.html', products=products, services=services)

# === Signup ===
@main.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.form
        if data['password'] != data['confirm_password']:
            return render_template('signup.html', error="Passwords do not match.")

        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return render_template('signup.html', error="Email already registered.")

        new_user = User(
            full_name=data['full_name'],
            birthdate=data['birthdate'],
            age=int(data['age']),
            address=data['address'],
            contact=data['contact'],
            email=data['email'],
            password=generate_password_hash(data['password'], method='pbkdf2:sha256'),
            is_admin=False
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('main.login'))

    return render_template('signup.html')


# === Login ===
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('main.admin_dashboard'))
            return redirect(url_for('main.base'))
        flash('Invalid credentials')
    return render_template('login.html')


# === Logout ===
@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))


# === Book ===
@main.route('/book', methods=['GET', 'POST'], endpoint='book_service')
@main.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    if request.method == 'POST':
        service_name = request.form.get('service')
        date_str = request.form.get('date')
        time = request.form.get('time')

        if not all([service_name, date_str, time]):
            flash("Missing booking details.", "error")
            return redirect(url_for('main.book', service=service_name))

        service = Service.query.filter_by(name=service_name).first()
        if not service:
            flash("Service not found.", "error")
            return redirect(url_for('main.book'))

        timestamp = datetime.strptime(f"{date_str} {time}", "%Y-%m-%d %H:%M")

        # Check for conflict
        existing = Booking.query.filter_by(date=date_str, time=time).first()
        if existing:
            flash("Time slot already booked.", "error")
            return redirect(url_for('main.book', service=service_name))

        order_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        booking = Booking(
            user_id=current_user.id,
            service=service.name,
            date=date_str,
            time=time,
            timestamp=datetime.utcnow(),
            order_code=order_code,
            status='pending',
            price=service.price
        )
        db.session.add(booking)
        db.session.commit()

        return redirect(url_for('main.receipt', order_code=order_code))

    # GET request
    service_param = request.args.get('service')
    selected_service = None
    if service_param:
        selected_service = Service.query.filter_by(name=service_param).first()

    return render_template('book.html', selected_service=selected_service, today=date.today())

# === Receipt View ===
@main.route('/receipt/<order_code>')
@login_required
def receipt(order_code):
    # Check if it's a product order
    order = Order.query.filter_by(order_code=order_code).first()
    if order:
        return render_template('receipt.html', order=order, order_code=order_code)

    # Otherwise, it's a service booking
    booking = Booking.query.filter_by(order_code=order_code).first_or_404()
    return render_template('service_receipt.html', order=booking, order_code=order_code)


# === Profile ===
@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form['full_name']
        current_user.birthdate = request.form['birthdate']
        current_user.age = request.form['age']
        current_user.address = request.form['address']
        current_user.contact = request.form['contact']
        db.session.commit()
        flash("Profile updated.")

    # Bookings
    active_bookings = Booking.query.filter_by(user_id=current_user.id).filter(Booking.status != 'completed').all()
    history = Booking.query.filter_by(user_id=current_user.id, status='completed').all()

    # Orders
    pending_orders = Order.query.filter_by(user_id=current_user.id, status='pending').all()
    completed_orders = Order.query.filter_by(user_id=current_user.id, status='paid').all()

    return render_template('profile.html',
                           active_bookings=active_bookings,
                           history=history,
                           pending_orders=pending_orders,
                           completed_orders=completed_orders)

# === Admin Dashboard ===
@main.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role not in ['Barber','Receptionist', 'Manager', 'Admin']:
        abort(403)
    bookings = Booking.query.order_by(Booking.timestamp.desc()).all()
    orders = Order.query.order_by(Order.timestamp.desc()).all()
    products = Product.query.all()
    services = Service.query.all()
    return render_template('admin_dashboard.html', products=products, bookings=bookings, services=services, orders=orders)


# === Add Product (Admin) ===
@main.route('/admin/add_product', methods=['POST'])
@login_required
def add_product():
    if current_user.role not in ['Receptionist', 'Manager', 'Admin']:
        abort(403)

    data = request.form
    file = request.files.get('image')

    filename = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        os.makedirs(PRODUCT_UPLOAD_FOLDER, exist_ok=True)
        file.save(os.path.join(PRODUCT_UPLOAD_FOLDER, filename))

    new_product = Product(
        name=data['name'],
        description=data['description'],
        price=float(data['price']),
        stock=int(data['stock']),
        image=filename
    )
    db.session.add(new_product)
    db.session.commit()
    return redirect(url_for('main.admin_dashboard'))


# === Edit Product ===
@main.route('/admin/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if current_user.role not in ['Receptionist', 'Manager', 'Admin']:
        abort(403)
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.stock = int(request.form['stock'])

        file = request.files.get('image')
        if file and file.filename:
            filename = secure_filename(file.filename)
            os.makedirs(PRODUCT_UPLOAD_FOLDER, exist_ok=True)
            file.save(os.path.join(PRODUCT_UPLOAD_FOLDER, filename))
            product.image = filename

        db.session.commit()
        return redirect(url_for('main.admin_dashboard'))

    return render_template('edit_product.html', product=product)


# === Checkout ===
@main.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart = request.get_json()
    if not cart:
        return jsonify({'success': False, 'message': 'Cart is empty'})

    order_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    total = 0
    order = Order(user_id=current_user.id, order_code=order_code, total=0)
    db.session.add(order)
    db.session.flush()

    for pid, item in cart.items():
        product = Product.query.get(int(pid))
        qty = int(item['qty'])
        subtotal = product.price * qty
        total += subtotal

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=qty,
            subtotal=subtotal
        )
        product.stock -= qty
        db.session.add(order_item)

    order.total = total
    db.session.commit()

    # ✅ Generate QR code instead of barcode
    os.makedirs(QR_FOLDER, exist_ok=True)
    qr = qrcode.make(order_code)
    qr_path = os.path.join(QR_FOLDER, f"{order_code}.png")
    qr.save(qr_path)

    return jsonify({'success': True, 'order_code': order_code})


@main.route('/service_receipt/<order_code>')
@login_required
def service_receipt(order_code):
    booking = Booking.query.filter_by(order_code=order_code).first_or_404()
    return render_template('service_receipt.html', order=booking)

# === Service ===

@main.route('/admin/add_service', methods=['POST'])
@login_required
def add_service():
    if current_user.role not in ['Receptionist', 'Manager', 'Admin']:
        abort(403)

    data = request.form
    file = request.files.get('image')
    filename = None

    if file and file.filename:
        filename = secure_filename(file.filename)
        os.makedirs(SERVICE_UPLOAD_FOLDER, exist_ok=True)
        file.save(os.path.join(SERVICE_UPLOAD_FOLDER, filename))

    new_service = Service(
        name=data['name'],
        description=data['description'],
        price=float(data['price']),
        image=filename
    )

    db.session.add(new_service)
    db.session.commit()

    return redirect(url_for('main.admin_dashboard'))


@main.route('/admin/edit_service/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_service(id):
    if current_user.role not in ['Receptionist', 'Manager', 'Admin']:
        abort(403)

    service = Service.query.get_or_404(id)

    if request.method == 'POST':
        service.name = request.form['name']
        service.description = request.form['description']
        service.price = float(request.form['price'])

        file = request.files.get('image')
        if file and file.filename:
            filename = secure_filename(file.filename)
            service_path = os.path.join('app/static/uploads/services', filename)
            os.makedirs(os.path.dirname(service_path), exist_ok=True)
            file.save(service_path)
            service.image = filename

        db.session.commit()
        flash("Service updated successfully.")
        return redirect(url_for('main.admin_dashboard'))

    return render_template('edit_service.html', service=service)

@main.route('/admin/delete_service/<int:id>', methods=['POST'])
@login_required
def delete_service(id):
    if current_user.role not in ['Receptionist', 'Manager', 'Admin']:
        abort(403)

    service = Service.query.get_or_404(id)
    db.session.delete(service)
    db.session.commit()
    return redirect(url_for('main.admin_dashboard'))

@main.route('/admin/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if current_user.role not in ['Receptionist', 'Manager', 'Admin']:
        abort(403)

    product = Product.query.get_or_404(product_id)

    # Optionally remove image from static/uploads
    if product.image:
        image_path = os.path.join(PRODUCT_UPLOAD_FOLDER, product.image)
        if os.path.exists(image_path):
            os.remove(image_path)

    db.session.delete(product)
    db.session.commit()
    flash("Product deleted successfully.", "success")
    return redirect(url_for('main.admin_dashboard'))



@main.route('/bookings')
@login_required
def bookings():
    if current_user.role not in ['Barber', 'Manager', 'Admin']:
        abort(403)

    manila = timezone('Asia/Manila')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    bookings_query = Booking.query.order_by(Booking.timestamp.desc())
    paginated = bookings_query.paginate(page=page, per_page=per_page)

    # Apply Manila timezone to each booking's timestamp
    for b in paginated.items:
        b.local_time = b.timestamp.astimezone(manila).strftime('%Y-%m-%d %I:%M %p')

    return render_template('bookings.html', bookings=paginated)


# BULK DELETE ROUTE
@main.route('/delete_bookings', methods=['POST'])
@login_required
def delete_bookings():
    if current_user.role not in ['Admin', 'Manager']:
        abort(403)

    ids = request.form.getlist('booking_ids')
    if ids:
        for bid in ids:
            booking = Booking.query.get(int(bid))
            if booking:
                db.session.delete(booking)
        db.session.commit()
        flash(f"{len(ids)} booking(s) deleted.", "success")
    else:
        flash("No bookings selected for deletion.", "error")

    return redirect(url_for('main.bookings'))


@main.route('/api/pending-bookings', methods=['GET'])
@login_required
def get_pending_bookings():
    bookings = Booking.query.filter_by(status='pending').all()
    return jsonify([
        {
            'id': b.id,
            'client_name': b.client_name,
            'service': b.service,
            'datetime': b.datetime.isoformat(),
            'status': b.status
        } for b in bookings
    ])

@main.route('/api/update-booking', methods=['POST'])
@login_required
def update_booking():
    data = request.get_json()
    booking_id = data.get('id')
    new_status = data.get('status')

    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({'message': 'Booking not found'}), 404

    booking.status = new_status
    db.session.commit()
    return jsonify({'message': f'Booking {new_status}'}), 200

@main.route('/update-booking-status', methods=['POST'])
@login_required
def update_booking_status():
    if current_user.role not in ['Barber', 'Manager', 'Admin']:
        abort(403)

    booking_id = request.form.get('id')
    new_status = request.form.get('status')

    booking = Booking.query.get_or_404(booking_id)
    
    if new_status == 'accepted' and current_user.role == 'Barber':
        booking.status = 'accepted'
        booking.barber_id = current_user.id  # ✅ Assign barber here
    elif new_status == 'declined':
        booking.status = 'declined'

    db.session.commit()
    return redirect(url_for('main.bookings'))

@main.route('/sales')
@login_required
def sales():
    if current_user.role not in ['Receptionist', 'Manager', 'Admin']:
        abort(403)

    start = request.args.get('start')
    end = request.args.get('end')

    if start and end:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
        orders = Order.query.filter(Order.status == 'paid', Order.timestamp.between(start_date, end_date)).all()
        bookings = Booking.query.filter(Booking.status == 'accepted', Booking.timestamp.between(start_date, end_date)).all()
    else:
        orders = Order.query.filter(Order.status == 'paid').all()
        bookings = Booking.query.filter(Booking.status == 'accepted').all()
        all_timestamps = [o.timestamp.date() for o in orders] + [b.timestamp.date() for b in bookings]
        if all_timestamps:
            start_date = min(all_timestamps)
            end_date = max(all_timestamps)
        else:
            start_date = end_date = date.today()

    total_sales = sum(order.total for order in orders) + sum(booking.price or 0 for booking in bookings)
    total_orders = len(orders) + len(bookings)

    # Full date range
    date_range = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    revenue_by_date = {d: {'orders': 0, 'bookings': 0} for d in date_range}

    for order in orders:
        key = order.timestamp.date()
        revenue_by_date[key]['orders'] += order.total

    for booking in bookings:
        key = booking.timestamp.date()
        revenue_by_date[key]['bookings'] += booking.price or 0

    labels = [d.strftime('%Y-%m-%d') for d in date_range]
    order_values = [revenue_by_date[d]['orders'] for d in date_range]
    booking_values = [revenue_by_date[d]['bookings'] for d in date_range]

    top = (
        db.session.query(OrderItem.product_id, func.sum(OrderItem.quantity))
        .group_by(OrderItem.product_id)
        .order_by(func.sum(OrderItem.quantity).desc())
        .first()
    )
    best_seller = Product.query.get(top[0]).name if top else None

    return render_template(
        'reports.html',
        orders=orders,
        bookings=bookings,
        total_sales=round(total_sales, 2),
        total_orders=total_orders,
        best_seller=best_seller,
        labels=labels,
        order_values=order_values,
        booking_values=booking_values
    )

@main.route('/export_sales')
@login_required
def export_sales():
    if current_user.role not in ['Receptionist', 'Manager', 'Admin']:
        abort(403)

    # Get date range from query
    start = request.args.get('start')
    end = request.args.get('end')
    start_date = datetime.strptime(start, "%Y-%m-%d").date() if start else date.today()
    end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else date.today()

    # Get orders and bookings in range
    orders = Order.query.filter(Order.status == 'paid', Order.timestamp.between(start_date, end_date)).all()
    bookings = Booking.query.filter(Booking.status == 'accepted', Booking.timestamp.between(start_date, end_date)).all()

    # Combine into a single list of dicts
    rows = []

    for o in orders:
        rows.append({
            'Date': o.timestamp.strftime('%Y-%m-%d'),
            'Order Code': o.order_code,
            'Client': o.user.full_name,
            'Amount': o.total,
            'Status': o.status
        })

    for b in bookings:
        rows.append({
            'Date': b.timestamp.strftime('%Y-%m-%d'),
            'Order Code': b.order_code,
            'Client': b.user.full_name,
            'Amount': b.price or 0,
            'Status': b.status
        })

    # Generate Excel file
    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sales')
    output.seek(0)

    return send_file(output,
                     download_name='sales_report.xlsx',
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@main.route('/roles')
@login_required
def roles():
    if current_user.role not in ['Manager', 'Admin']:
        abort(403)
    employees = User.query.filter_by(is_admin=False).all()
    return render_template('employees.html', employees=employees)

@main.route('/add-employee', methods=['POST'])
@login_required
def add_employee():
    if current_user.role not in ['Manager', 'Admin']:
        abort(403)
    full_name = request.form['full_name']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']

    if User.query.filter_by(email=email).first():
        flash("Email already exists.", "danger")
        return redirect(url_for('main.roles'))

    new_user = User(
        full_name=full_name,
        email=email,
        password=generate_password_hash(password, method='pbkdf2:sha256'),
        role=role,
        is_admin=False
    )
    db.session.add(new_user)
    db.session.commit()
    flash("Employee account created!", "success")
    return redirect(url_for('main.roles'))

@main.route('/verify_order/<order_code>')
@login_required
def verify_order(order_code):
    order = Order.query.filter_by(order_code=order_code).first()
    if not order or order.status == 'paid':
        return jsonify({'success': False})
    
    return jsonify({'success': True, 'order': {
        'order_code': order.order_code,
        'total': round(order.total, 2)
    }})

@main.route('/payment')
@login_required
def payment():
    if current_user.role not in ['Receptionist','Manager', 'Admin']:
        abort(403)
    unpaid_orders = Order.query.filter_by(status='pending').all()
    return render_template('payments.html', unpaid_orders=unpaid_orders)


@main.route('/confirm_payment', methods=['POST'])
@login_required
def confirm_payment():
    if current_user.role not in ['Receptionist','Manager', 'Admin']:
        abort(403)
    order_code = request.form.get('order_code')
    order = Order.query.filter_by(order_code=order_code).first()

    if not order:
        flash('Invalid order code.', 'error')
    else:
        order.status = 'paid'
        db.session.commit()
        flash(f'Order {order_code} has been marked as paid.', 'success')

    return redirect(url_for('main.payment'))

@main.route('/check_conflict', methods=['POST'])
@login_required
def check_conflict():
    data = request.get_json()
    date = data.get('date')
    time = data.get('time')

    conflict = Booking.query.filter_by(date=date, time=time).first()
    return jsonify({'conflict': bool(conflict)})
