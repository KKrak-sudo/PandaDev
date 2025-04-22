from main import app, db, User
from sqlalchemy import Column, Boolean, String

def upgrade_database():
    with app.app_context():
        # Проверяем, существуют ли колонки
        db.session.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE')
        db.session.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason VARCHAR(200)')
        db.session.commit()
        print("Миграция успешно выполнена!")

if __name__ == "__main__":
    upgrade_database()