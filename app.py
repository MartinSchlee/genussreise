import os
import re
from datetime import datetime
from flask import Flask, render_template, url_for, flash, redirect, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'genussreise-master-final-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///genussreise.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

ADMIN_SECRET_KEY = "GEHEIM123"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Deutsche Systemmeldungen
login_manager.login_message = "Bitte melde dich an, um auf diese Seite zuzugreifen."
login_manager.login_message_category = "info"

# --- MODELLE ---

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    recipes = db.relationship('Recipe', backref='author', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='author', lazy=True, cascade="all, delete-orphan")
    favorites = db.relationship('Favorite', backref='user', lazy=True, cascade="all, delete-orphan")

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    recipes = db.relationship('Recipe', backref='category_rel', lazy=True)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    prep_time = db.Column(db.Integer, default=0)
    cook_time = db.Column(db.Integer, default=0)
    rest_time = db.Column(db.Integer, default=0)
    servings = db.Column(db.Integer, default=1)
    calories = db.Column(db.Integer, default=0)
    protein = db.Column(db.Float, default=0.0)
    carbs = db.Column(db.Float, default=0.0)
    fat = db.Column(db.Float, default=0.0)
    rating_sum = db.Column(db.Integer, default=0)
    rating_count = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    ingredients = db.relationship('Ingredient', backref='recipe', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='recipe', lazy=True, cascade="all, delete-orphan")

    @property
    def total_time_formatted(self):
        total = (self.prep_time or 0) + (self.cook_time or 0) + (self.rest_time or 0)
        if total == 0: return "k.A."
        if total >= 60:
            h, m = total // 60, total % 60
            return f"{h} Std. {m} Min." if m > 0 else f"{h} Std."
        return f"{total} Min."

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.String(50))
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_categories():
    return dict(all_categories=Category.query.order_by(Category.name).all())

# --- ROUTEN ---

@app.route("/")
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search')
    if search:
        pagination = Recipe.query.filter((Recipe.name.contains(search)) | (Recipe.instructions.contains(search))).order_by(Recipe.id.desc()).paginate(page=page, per_page=9)
    else:
        pagination = Recipe.query.order_by(Recipe.id.desc()).paginate(page=page, per_page=9)
    for r in pagination.items:
        r.avg_rating = round(r.rating_sum / r.rating_count, 1) if r.rating_count > 0 else 0
    return render_template('index.html', recipes=pagination, search_query=search)

@app.route("/category/<int:category_id>")
def recipes_in_category(category_id):
    page = request.args.get('page', 1, type=int)
    cat = Category.query.get_or_404(category_id)
    pagination = Recipe.query.filter_by(category_id=category_id).order_by(Recipe.id.desc()).paginate(page=page, per_page=9)
    for r in pagination.items:
        r