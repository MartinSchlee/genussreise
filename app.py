import os
from flask import Flask, render_template, url_for, flash, redirect, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'genuss-reise-2026-final-fixed'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///genussreise.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

ADMIN_SECRET_KEY = "GEHEIM123"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELLE ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    recipes = db.relationship('Recipe', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

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
    recipes = Recipe.query.all()
    for r in recipes:
        r.avg_rating = round(r.rating_sum / r.rating_count, 1) if r.rating_count > 0 else 0
    return render_template('index.html', recipes=recipes)

@app.route("/category/<int:category_id>")
def recipes_in_category(category_id):
    category = Category.query.get_or_404(category_id)
    recipes = Recipe.query.filter_by(category_id=category_id).all()
    for r in recipes:
        r.avg_rating = round(r.rating_sum / r.rating_count, 1) if r.rating_count > 0 else 0
    return render_template('index.html', recipes=recipes, current_category=category)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        flash('Login fehlgeschlagen.', 'danger')
    return render_template('login.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form.get('password'))
        is_admin = (request.form.get('admin_key') == ADMIN_SECRET_KEY)
        user = User(username=request.form.get('username'), email=request.form.get('email'), password=hashed_pw, is_admin=is_admin)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route("/forgot-password")
def forgot_password():
    return "Bitte wende dich an den Admin. <a href='/login'>Zurück</a>"

@app.route("/recipe/new", methods=['GET', 'POST'])
@login_required
def add_recipe():
    if request.method == 'POST':
        file = request.files.get('recipe_image')
        filename = 'default.jpg'
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        recipe = Recipe(
            name=request.form.get('recipe_name'),
            instructions=request.form.get('instructions'),
            category_id=request.form.get('category_id'),
            image_file=filename,
            author=current_user,
            prep_time=request.form.get('prep_time') or 0,
            cook_time=request.form.get('cook_time') or 0,
            rest_time=request.form.get('rest_time') or 0,
            servings=request.form.get('servings') or 1,
            calories=request.form.get('calories') or 0,
            protein=request.form.get('protein') or 0,
            carbs=request.form.get('carbs') or 0,
            fat=request.form.get('fat') or 0
        )
        db.session.add(recipe)
        db.session.flush()
        
        ing_names = request.form.getlist('ing_name[]')
        ing_amounts = request.form.getlist('ing_amount[]')
        for name, amount in zip(ing_names, ing_amounts):
            if name.strip():
                ing = Ingredient(name=name, amount=amount, recipe_id=recipe.id)
                db.session.add(ing)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_recipe.html')

@app.route("/recipe/<int:recipe_id>", methods=['GET', 'POST'])
def recipe_detail(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if request.method == 'POST' and current_user.is_authenticated:
        rating = request.form.get('rating')
        content = request.form.get('content')
        if rating or content:
            r_val = int(rating) if rating else None
            comment = Comment(content=content, rating=r_val, author=current_user, recipe=recipe)
            if r_val:
                recipe.rating_sum += r_val
                recipe.rating_count += 1
            db.session.add(comment)
            db.session.commit()
            return redirect(url_for('recipe_detail', recipe_id=recipe.id))
    
    avg_rating = round(recipe.rating_sum / recipe.rating_count, 1) if recipe.rating_count > 0 else 0
    return render_template('recipe_detail.html', recipe=recipe, avg_rating=avg_rating)

@app.route("/recipe/<int:recipe_id>/edit", methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.author != current_user and not current_user.is_admin:
        abort(403)
    
    if request.method == 'POST':
        file = request.files.get('recipe_image')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            recipe.image_file = filename

        recipe.name = request.form.get('recipe_name')
        recipe.instructions = request.form.get('instructions')
        recipe.category_id = request.form.get('category_id')
        recipe.prep_time = request.form.get('prep_time') or 0
        recipe.cook_time = request.form.get('cook_time') or 0
        recipe.rest_time = request.form.get('rest_time') or 0
        recipe.servings = request.form.get('servings') or 1
        recipe.calories = request.form.get('calories') or 0
        recipe.protein = request.form.get('protein') or 0
        recipe.carbs = request.form.get('carbs') or 0
        recipe.fat = request.form.get('fat') or 0

        # Zutaten Reset
        Ingredient.query.filter_by(recipe_id=recipe.id).delete()
        ing_names = request.form.getlist('ing_name[]')
        ing_amounts = request.form.getlist('ing_amount[]')
        for name, amount in zip(ing_names, ing_amounts):
            if name.strip():
                ing = Ingredient(name=name, amount=amount, recipe_id=recipe.id)
                db.session.add(ing)
        
        db.session.commit()
        flash('Rezept aktualisiert!', 'success')
        return redirect(url_for('recipe_detail', recipe_id=recipe.id))
    
    return render_template('edit_recipe.html', recipe=recipe)

@app.route("/recipe/<int:recipe_id>/delete", methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if current_user.is_admin:
        db.session.delete(recipe)
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Category.query.first():
            cat_list = sorted(["Vorspeise", "Hauptspeise", "Dessert", "Frühstück", "Snack", "Vegan", "Vegetarisch", "Backen", "Getränke", "Salate", "Suppen", "Pasta & Nudeln", "Fleisch", "Fisch", "Schnelle Küche", "Asiatisch", "Italienisch", "Mediterran", "Aufläufe", "Eintöpfe", "Saucen & Dips", "Fingerfood", "Low Carb", "Gesund & Fit", "Meeresfrüchte"])
            for name in cat_list:
                db.session.add(Category(name=name))
            db.session.commit()
    app.run(debug=True)