from main import SessionLocal, User, hash_password

username = "admin"
password = "my_secret_pass"

db = SessionLocal()

# Проверка: есть ли уже такой пользователь
existing = db.query(User).filter_by(username=username).first()
if existing:
    print("⚠️ Такой пользователь уже есть.")
else:
    user = User(
        username=username,
        password=hash_password(password),
        is_admin=True
    )
    db.add(user)
    db.commit()
    print("✅ Админ создан!")

db.close()
