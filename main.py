from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import hashlib
import os
from datetime import datetime

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

def get_current_user(request: Request, db: Session) -> Optional[User]:
    user_id = request.session.get("user_id")
    if user_id:
        return db.query(User).filter(User.id == user_id).first()
    return None

# Routes
@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, db: Session = Depends(get_db)):
    news = db.query(News).order_by(News.id.desc()).all()
    categories = db.query(Category).order_by(Category.name).all()
    user = get_current_user(request, db)
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "news": news, "user": user, "categories": categories}
    )

@app.get("/category/{category_id}", response_class=HTMLResponse)
async def category_page(request: Request, category_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter_by(id=category_id).first()
    if not category:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    news = db.query(News).filter_by(category_id=category_id).order_by(News.id.desc()).all()
    categories = db.query(Category).order_by(Category.name).all()
    user = get_current_user(request, db)
    
    return templates.TemplateResponse(
        "category.html", 
        {
            "request": request, 
            "news": news, 
            "user": user, 
            "category": category,
            "categories": categories
        }
    )

@app.get("/register", response_class=HTMLResponse)
async def register_get(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        "register.html", 
        {"request": request, "error": None}
    )

@app.post("/register")
async def register_post(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...),
    email: str = Form(None),
    db: Session = Depends(get_db)
):
    # Check if username already exists
    if db.query(User).filter_by(username=username).first():
        return templates.TemplateResponse(
            "register.html", 
            {"request": request, "error": "Пользователь с таким именем уже существует"}
        )
    
    # Check if email already exists (if provided)
    if email and db.query(User).filter_by(email=email).first():
        return templates.TemplateResponse(
            "register.html", 
            {"request": request, "error": "Этот email уже зарегистрирован"}
        )
    
    # Create new user
    user = User(username=username, password=hash_password(password), email=email)
    db.add(user)
    db.commit()
    
    # Redirect to login page
    return RedirectResponse("/login?registered=true", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, registered: bool = False, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        "login.html", 
        {"request": request, "registered": registered, "error": None}
    )

@app.post("/login")
async def login_post(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = db.query(User).filter_by(
        username=username, 
        password=hash_password(password)
    ).first()
    
    if user:
        request.session["user_id"] = user.id
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        "login.html", 
        {"request": request, "registered": False, "error": "Неверное имя пользователя или пароль"}
    )

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    news = db.query(News).order_by(News.id.desc()).all()
    categories = db.query(Category).order_by(Category.name).all()
    return templates.TemplateResponse(
        "admin.html", 
        {"request": request, "news": news, "user": user, "categories": categories}
    )

@app.get("/admin/categories", response_class=HTMLResponse)
async def admin_categories(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    categories = db.query(Category).order_by(Category.name).all()
    return templates.TemplateResponse(
        "admin_categories.html", 
        {"request": request, "categories": categories, "user": user}
    )

@app.post("/admin/categories")
async def add_category(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    # Проверка на существование категории
    if db.query(Category).filter_by(name=name).first():
        return templates.TemplateResponse(
            "admin_categories.html",
            {
                "request": request, 
                "error": "Категория с таким именем уже существует",
                "categories": db.query(Category).order_by(Category.name).all(),
                "user": user
            }
        )
    
    new_category = Category(name=name, description=description)
    db.add(new_category)
    db.commit()
    
    return RedirectResponse("/admin/categories", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/categories/{category_id}/delete")
async def delete_category(
    request: Request,
    category_id: int,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    category = db.query(Category).filter_by(id=category_id).first()
    if category:
        # Удаляем связь с новостями
        news_items = db.query(News).filter_by(category_id=category_id).all()
        for item in news_items:
            item.category_id = None
        
        db.delete(category)
        db.commit()
    
    return RedirectResponse("/admin/categories", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/news")
async def add_news(
    request: Request, 
    title: str = Form(...), 
    content: str = Form(...),
    category_id: int = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    new_post = News(
        title=title, 
        content=content, 
        author_id=user.id,
        category_id=category_id
    )
    db.add(new_post)
    db.commit()
    
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/news/{news_id}/delete")
async def delete_news(
    request: Request, 
    news_id: int, 
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    news = db.query(News).filter_by(id=news_id).first()
    if news:
        db.delete(news)
        db.commit()
    
    return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)

# Run the application
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
