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

# Create admin when app starts
with app.app_context():
    create_admin()

# Run the application
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)