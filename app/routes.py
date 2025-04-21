from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
from . import db, login_manager
from .models import Service, User, Booking, Product, Order, OrderItem
import os, random, string, barcode
from barcode.writer import ImageWriter

main = Blueprint('main', __name__)

PRODUCT_UPLOAD_FOLDER = 'app/static/uploads/products'
SERVICE_UPLOAD_FOLDER = 'app/static/uploads/services'
BARCODE_FOLDER = 'app/static/barcodes'


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
            flash("Incomplete booking details.", "error")
            return redirect(url_for('main.book', service=service_name))

        selected_service = Service.query.filter_by(name=service_name).first()
        if not selected_service:
            flash("Selected service not found.", "error")
            return redirect(url_for('main.book'))

        try:
            timestamp = datetime.strptime(f"{date_str} {time}", "%Y-%m-%d %H:%M")
        except:
            flash("Invalid date/time format.", "error")
            return redirect(url_for('main.book', service=service_name))

        # Check for booking conflicts
        existing = Booking.query.filter_by(date=date_str, time=time).first()
        if existing:
            flash("This time slot is already booked.", "error")
            return render_template('book.html', selected_service=selected_service, today=date.today())

        # Generate unique order code
        order_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        # Save booking
        new_booking = Booking(
            user_id=current_user.id,
            service=selected_service.name,
            date=date_str,
            time=time,
            order_code=order_code,
            status='pending'
        )
        db.session.add(new_booking)
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
        return render_template('receipt.html', order=order)

    # Otherwise, it's a service booking
    booking = Booking.query.filter_by(order_code=order_code).first_or_404()
    return render_template('service_receipt.html', order=booking)


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
        flash("Profile updated successfully!")
        return redirect(url_for('main.profile'))

    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.date.desc()).all()
    active = [b for b in bookings if b.status != 'paid']
    history = [b for b in bookings if b.status == 'paid']
    return render_template('profile.html', active_bookings=active, history=history)


# === Admin Dashboard ===
@main.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    bookings = Booking.query.order_by(Booking.timestamp.desc()).all()
    products = Product.query.all()
    services = Service.query.all()
    return render_template('admin_dashboard.html', products=products, bookings=bookings, services=services)


# === Add Product (Admin) ===
@main.route('/admin/add_product', methods=['POST'])
@login_required
def add_product():
    if not current_user.is_admin:
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
    if not current_user.is_admin:
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

    # generate barcode
    code = barcode.get_barcode_class('code128')(order_code, writer=ImageWriter())
    os.makedirs(BARCODE_FOLDER, exist_ok=True)
    code.save(os.path.join(BARCODE_FOLDER, order_code))

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
    if not current_user.is_admin:
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
    if not current_user.is_admin:
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
    if not current_user.is_admin:
        abort(403)

    service = Service.query.get_or_404(id)
    db.session.delete(service)
    db.session.commit()
    return redirect(url_for('main.admin_dashboard'))

@main.route('/admin/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if not current_user.is_admin:
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

