from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import hashlib
import os
import random
import string
import secrets
from datetime import datetime, timedelta

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "super-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Настройки для YooMoney
app.config["YOOMONEY_WALLET"] = "4100117513967646"  # Пример номера кошелька YooMoney

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Define database models
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256))
    email = db.Column(db.String(120), unique=True, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.String(200), nullable=True)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    news = db.relationship("News", backref="author", lazy=True)

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    news = db.relationship("News", backref="category", lazy=True)

class News(db.Model):
    __tablename__ = "news"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

# Создаем модель для пожертвований
class Donation(db.Model):
    __tablename__ = "donations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    payment_id = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default="pending")  # pending, completed, failed
    
    user = db.relationship("User", backref="donations")

# Create database tables
with app.app_context():
    db.create_all()

# Helper functions
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return User.query.get(user_id)
    return None

def generate_reset_token():
    """Генерирует случайный токен для восстановления пароля"""
    # Генерируем 6-значный числовой код
    reset_code = ''.join(random.choice(string.digits) for _ in range(6))
    return reset_code

def send_reset_email(user, token):
    """
    Отправляет email с кодом для восстановления пароля
    В боевом режиме здесь был бы код для отправки через SendGrid или другой сервис
    """
    # Имитация отправки письма для демонстрационных целей
    print(f"[ДЕМО] Отправка кода восстановления на email {user.email}: {token}")
    return True

# Routes
@app.route("/")
def homepage():
    news = News.query.order_by(News.id.desc()).all()
    categories = Category.query.order_by(Category.name).all()
    user = get_current_user()
    return render_template(
        "index.html", 
        news=news, 
        user=user, 
        categories=categories
    )

@app.route("/category/<int:category_id>")
def category_page(category_id):
    category = Category.query.get_or_404(category_id)
    news = News.query.filter_by(category_id=category_id).order_by(News.id.desc()).all()
    categories = Category.query.order_by(Category.name).all()
    user = get_current_user()
    
    return render_template(
        "category.html", 
        news=news, 
        user=user, 
        category=category,
        categories=categories
    )

@app.route("/register", methods=["GET"])
def register_get():
    user = get_current_user()
    if user:
        return redirect(url_for("homepage"))
    return render_template("register.html", error=None)

@app.route("/register", methods=["POST"])
def register_post():
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")
    
    # Check if username already exists
    if User.query.filter_by(username=username).first():
        return render_template(
            "register.html", 
            error="Пользователь с таким именем уже существует"
        )
    
    # Check if email already exists (if provided)
    if email and User.query.filter_by(email=email).first():
        return render_template(
            "register.html", 
            error="Этот email уже зарегистрирован"
        )
    
    # Create new user
    user = User(username=username, password=hash_password(password), email=email)
    db.session.add(user)
    db.session.commit()
    
    # Redirect to login page
    return redirect(url_for("login_get", registered=True))

@app.route("/login", methods=["GET"])
def login_get():
    user = get_current_user()
    if user:
        return redirect(url_for("homepage"))
    
    registered = request.args.get("registered", "false") == "true"
    return render_template("login.html", registered=registered, error=None)

@app.route("/login", methods=["POST"])
def login_post():
    username = request.form.get("username")
    password = request.form.get("password")
    
    user = User.query.filter_by(
        username=username, 
        password=hash_password(password)
    ).first()
    
    if user:
        # Проверяем, не заблокирован ли пользователь
        if user.is_banned:
            ban_message = "Ваш аккаунт заблокирован"
            if user.ban_reason:
                ban_message += f". Причина: {user.ban_reason}"
            return render_template(
                "login.html",
                registered=False,
                error=ban_message
            )
        
        session["user_id"] = user.id
        return redirect(url_for("homepage"))
    
    return render_template(
        "login.html", 
        registered=False, 
        error="Неверное имя пользователя или пароль"
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("homepage"))

@app.route("/admin")
def admin_panel():
    user = get_current_user()
    if not user or not user.is_admin:
        return redirect(url_for("homepage"))
    
    news = News.query.order_by(News.id.desc()).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "admin.html", 
        news=news, 
        user=user, 
        categories=categories
    )

@app.route("/admin/categories")
def admin_categories():
    user = get_current_user()
    if not user or not user.is_admin:
        return redirect(url_for("homepage"))
    
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "admin_categories.html", 
        categories=categories, 
        user=user,
        error=None
    )

@app.route("/admin/categories", methods=["POST"])
def add_category():
    user = get_current_user()
    if not user or not user.is_admin:
        return redirect(url_for("homepage"))
    
    name = request.form.get("name")
    description = request.form.get("description")
    
    # Проверка на существование категории
    if Category.query.filter_by(name=name).first():
        categories = Category.query.order_by(Category.name).all()
        return render_template(
            "admin_categories.html",
            error="Категория с таким именем уже существует",
            categories=categories,
            user=user
        )
    
    new_category = Category(name=name, description=description)
    db.session.add(new_category)
    db.session.commit()
    
    return redirect(url_for("admin_categories"))

@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id):
    user = get_current_user()
    if not user or not user.is_admin:
        return redirect(url_for("homepage"))
    
    category = Category.query.get(category_id)
    if category:
        # Удаляем связь с новостями
        news_items = News.query.filter_by(category_id=category_id).all()
        for item in news_items:
            item.category_id = None
        
        db.session.delete(category)
        db.session.commit()
    
    return redirect(url_for("admin_categories"))

@app.route("/admin/news", methods=["POST"])
def add_news():
    user = get_current_user()
    if not user or not user.is_admin:
        return redirect(url_for("homepage"))
    
    title = request.form.get("title")
    content = request.form.get("content")
    category_id = request.form.get("category_id")
    
    if category_id == "":
        category_id = None
    
    new_post = News(
        title=title, 
        content=content, 
        author_id=user.id,
        category_id=category_id
    )
    db.session.add(new_post)
    db.session.commit()
    
    return redirect(url_for("admin_panel"))

@app.route("/admin/news/<int:news_id>/delete", methods=["POST"])
def delete_news(news_id):
    user = get_current_user()
    if not user or not user.is_admin:
        return redirect(url_for("homepage"))
    
    news = News.query.get(news_id)
    if news:
        db.session.delete(news)
        db.session.commit()
    
    return redirect(url_for("admin_panel"))

# Create admin user function
def create_admin():
    admin = User.query.filter_by(username="root").first()
    if not admin:
        admin = User(
            username="root",
            password=hash_password("2344gr"),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Администратор 'root' успешно создан.")

# Личный кабинет
@app.route("/profile")
def profile():
    user = get_current_user()
    if not user:
        return redirect(url_for("login_get"))
    
    categories = Category.query.all()
    return render_template(
        "profile.html", 
        user=user, 
        categories=categories,
        error=None,
        success=None
    )

# Обновление email
@app.route("/update_email", methods=["POST"])
def update_email():
    user = get_current_user()
    if not user:
        return redirect(url_for("login_get"))
    
    email = request.form.get("email")
    password = request.form.get("password")
    
    # Проверка пароля
    if hash_password(password) != user.password:
        categories = Category.query.all()
        return render_template(
            "profile.html", 
            user=user, 
            categories=categories,
            error="Неверный пароль",
            success=None
        )
    
    # Проверка на существование email у другого пользователя
    if email != user.email and User.query.filter_by(email=email).first():
        categories = Category.query.all()
        return render_template(
            "profile.html", 
            user=user, 
            categories=categories,
            error="Этот email уже используется другим пользователем",
            success=None
        )
    
    user.email = email
    db.session.commit()
    
    categories = Category.query.all()
    return render_template(
        "profile.html", 
        user=user, 
        categories=categories,
        error=None,
        success="Email успешно обновлен"
    )

# Обновление пароля
@app.route("/update_password", methods=["POST"])
def update_password():
    user = get_current_user()
    if not user:
        return redirect(url_for("login_get"))
    
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    # Проверка текущего пароля
    if hash_password(current_password) != user.password:
        categories = Category.query.all()
        return render_template(
            "profile.html", 
            user=user, 
            categories=categories,
            error="Неверный текущий пароль",
            success=None
        )
    
    # Проверка совпадения новых паролей
    if new_password != confirm_password:
        categories = Category.query.all()
        return render_template(
            "profile.html", 
            user=user, 
            categories=categories,
            error="Новые пароли не совпадают",
            success=None
        )
    
    user.password = hash_password(new_password)
    db.session.commit()
    
    categories = Category.query.all()
    return render_template(
        "profile.html", 
        user=user, 
        categories=categories,
        error=None,
        success="Пароль успешно изменен"
    )

# Восстановление пароля - форма
@app.route("/forgot-password", methods=["GET"])
def forgot_password_get():
    categories = Category.query.all()
    return render_template(
        "forgot_password.html", 
        categories=categories,
        error=None,
        success=None
    )

# Восстановление пароля - отправка кода
@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    email = request.form.get("email")
    categories = Category.query.all()
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return render_template(
            "forgot_password.html", 
            categories=categories,
            error="Пользователь с таким email не найден",
            success=None
        )
    
    # Генерируем токен и устанавливаем срок действия
    token = generate_reset_token()
    user.reset_token = token
    user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()
    
    # Отправляем email с токеном (имитация)
    send_reset_email(user, token)
    
    return render_template(
        "forgot_password.html", 
        categories=categories,
        error=None,
        success=f"Код восстановления отправлен на {email}. Для демонстрации: {token}"
    )

# Сброс пароля - форма
@app.route("/reset-password/<token>", methods=["GET"])
def reset_password_get(token):
    categories = Category.query.all()
    return render_template(
        "reset_password.html", 
        token=token,
        categories=categories,
        error=None
    )

# Сброс пароля - обработка
@app.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    reset_code = request.form.get("reset_code")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    categories = Category.query.all()
    
    # Проверка совпадения новых паролей
    if new_password != confirm_password:
        return render_template(
            "reset_password.html", 
            token=token,
            categories=categories,
            error="Пароли не совпадают"
        )
    
    # Поиск пользователя с данным токеном
    user = User.query.filter_by(reset_token=reset_code).first()
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        return render_template(
            "reset_password.html", 
            token=token,
            categories=categories,
            error="Недействительный или истекший код восстановления"
        )
    
    # Обновление пароля
    user.password = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.session.commit()
    
    return redirect(url_for("login_get", reset=True))

# Пожертвования
@app.route("/donate")
def donate():
    user = get_current_user()
    categories = Category.query.all()
    
    return render_template(
        "donate.html", 
        user=user, 
        categories=categories
    )

# Обработка пожертвования
@app.route("/process-donation")
def process_donation():
    user = get_current_user()
    if not user:
        return redirect(url_for("login_get"))
    
    amount = request.args.get("amount", 100, type=float)
    
    # Создаем запись о пожертвовании
    donation = Donation(
        user_id=user.id,
        amount=amount
    )
    db.session.add(donation)
    db.session.commit()
    
    # Генерируем идентификатор платежа и готовим данные для YooMoney
    payment_id = f"donation_{donation.id}_{int(datetime.now().timestamp())}"
    wallet = app.config["YOOMONEY_WALLET"]
    
    # Отображаем страницу с информацией о платеже и номером кошелька
    return render_template(
        "payment.html", 
        user=user, 
        categories=Category.query.all(),
        donation=donation,
        payment_id=payment_id,
        wallet=wallet,
        amount=amount
    )

# Обработчик переключения темы
@app.route("/update_theme", methods=["POST"])
def update_theme():
    theme = request.json.get("theme", "dark-theme")
    session["theme"] = theme
    return jsonify({"status": "success"})

# Create admin when app starts
with app.app_context():
    create_admin()

# Run the application
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)