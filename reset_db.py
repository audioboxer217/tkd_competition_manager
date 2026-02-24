from app import app, db

# Create an application context
with app.app_context():
    db.drop_all()
    print("Database tables dropped in Supabase.")
    db.create_all()
    print("Database tables created in Supabase.")
