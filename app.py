from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

# This ensures the database tables are created
with app.app_context():
    db.create_all()  # ✅ Create tables if not existing

    # ✅ Create superadmin if not already there
    if not User.query.filter_by(email="admin@barbshop.com").first():
        superadmin = User(
            full_name="Super Admin",
            birthdate="1990-01-01",
            age=35,
            address="Admin HQ",
            contact="0000000000",
            email="admin@barbshop.com",
            password=generate_password_hash("supersecure", method='pbkdf2:sha256'),
            is_admin=True
        )
        db.session.add(superadmin)
        db.session.commit()
        print("✅ Superadmin created!")
    else:
        print("ℹ️ Superadmin already exists.")

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
