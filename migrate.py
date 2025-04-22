from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db = SQLAlchemy(app)

def upgrade_database():
    with app.app_context():
        # Проверяем, существуют ли колонки и добавляем их, если нет
        conn = db.engine.connect()
        try:
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE'))
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason VARCHAR(200)'))
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(100)'))
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expiry TIMESTAMP'))
            conn.commit()
            print("Миграция успешно выполнена!")
        except Exception as e:
            print(f"Ошибка при миграции: {e}")
            conn.rollback()
        finally:
            conn.close()

if __name__ == "__main__":
    upgrade_database()