import os
import re
from datetime import datetime
from flask import Flask, render_template, url_for, flash, redirect, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'genussreise-pagination-master-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///genussreise.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

ADMIN_SECRET_KEY = "GEHEIM123"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
# --- DIESE BEIDEN ZEILEN HINZUFÜGEN ---
login_manager.login_message = "Bitte melde dich an, um auf diese Seite zuzugreifen."
login_manager.login_message_category = "info" 
# --------------------------------------
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
        r.avg_rating = round(r.rating_sum / r.rating_count, 1) if r.rating_count > 0 else 0
    return render_template('index.html', recipes=pagination, current_category=cat)

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
        email, username = request.form.get('email'), request.form.get('username')
        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash('Nutzer existiert bereits.', 'warning')
            return render_template('register.html')
        hashed = generate_password_hash(request.form.get('password'))
        db.session.add(User(username=username, email=email, password=hashed, is_admin=(request.form.get('admin_key') == ADMIN_SECRET_KEY)))
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route("/profile")
@login_required
def profile():
    return render_template('profile.html')

@app.route("/user/delete", methods=['POST'])
@login_required
def delete_user():
    u = current_user
    logout_user()
    db.session.delete(u)
    db.session.commit()
    return redirect(url_for('index'))

@app.route("/forgot-password", methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST': flash('Simulation: Link gesendet.', 'info'); return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route("/recipe/new", methods=['GET', 'POST'])
@login_required
def add_recipe():
    if request.method == 'POST':
        file = request.files.get('recipe_image')
        fname = secure_filename(file.filename) if file and file.filename != '' else 'default.jpg'
        if fname != 'default.jpg': file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        recipe = Recipe(
            name=request.form.get('recipe_name'), instructions=request.form.get('instructions'),
            category_id=request.form.get('category_id'), image_file=fname, author=current_user,
            prep_time=int(request.form.get('prep_time') or 0), cook_time=int(request.form.get('cook_time') or 0),
            rest_time=int(request.form.get('rest_time') or 0), servings=int(request.form.get('servings') or 1),
            calories=int(request.form.get('calories') or 0), protein=float(request.form.get('protein') or 0),
            carbs=float(request.form.get('carbs') or 0), fat=float(request.form.get('fat') or 0)
        )
        db.session.add(recipe)
        db.session.flush()
        names, amounts = request.form.getlist('ing_name[]'), request.form.getlist('ing_amount[]')
        for n, a in zip(names, amounts):
            if n.strip(): db.session.add(Ingredient(name=n, amount=a, recipe_id=recipe.id))
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_recipe.html')

@app.route("/recipe/<int:recipe_id>", methods=['GET', 'POST'])
def recipe_detail(recipe_id):
    r = Recipe.query.get_or_404(recipe_id)
    is_fav = Favorite.query.filter_by(user_id=current_user.id, recipe_id=r.id).first() is not None if current_user.is_authenticated else False
    if request.method == 'POST' and current_user.is_authenticated:
        rating = request.form.get('rating')
        db.session.add(Comment(content=request.form.get('content'), rating=int(rating) if rating else None, author=current_user, recipe=r))
        if rating: r.rating_sum += int(rating); r.rating_count += 1
        db.session.commit()
        return redirect(url_for('recipe_detail', recipe_id=r.id))
    avg = round(r.rating_sum / r.rating_count, 1) if r.rating_count > 0 else 0
    return render_template('recipe_detail.html', recipe=r, avg_rating=avg, is_fav=is_fav)

@app.route("/recipe/<int:recipe_id>/edit", methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.author != current_user and not current_user.is_admin: abort(403)
    if request.method == 'POST':
        file = request.files.get('recipe_image')
        if file and file.filename != '':
            fname = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            recipe.image_file = fname
        recipe.name, recipe.instructions = request.form.get('recipe_name'), request.form.get('instructions')
        recipe.category_id = request.form.get('category_id')
        recipe.prep_time, recipe.cook_time, recipe.rest_time = int(request.form.get('prep_time') or 0), int(request.form.get('cook_time') or 0), int(request.form.get('rest_time') or 0)
        recipe.servings, recipe.calories = int(request.form.get('servings') or 1), int(request.form.get('calories') or 0)
        recipe.protein, recipe.carbs, recipe.fat = float(request.form.get('protein') or 0), float(request.form.get('carbs') or 0), float(request.form.get('fat') or 0)
        Ingredient.query.filter_by(recipe_id=recipe.id).delete()
        names, amounts = request.form.getlist('ing_name[]'), request.form.getlist('ing_amount[]')
        for n, a in zip(names, amounts):
            if n.strip(): db.session.add(Ingredient(name=n, amount=a, recipe_id=recipe.id))
        db.session.commit()
        return redirect(url_for('recipe_detail', recipe_id=recipe.id))
    return render_template('add_recipe.html', recipe=recipe)

@app.route("/recipe/<int:recipe_id>/delete", methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if current_user.is_admin or recipe.author == current_user:
        db.session.delete(recipe); db.session.commit()
        flash('Rezept gelöscht.', 'success')
    return redirect(url_for('index'))

@app.route("/favorite/<int:recipe_id>", methods=['POST'])
@login_required
def toggle_favorite(recipe_id):
    fav = Favorite.query.filter_by(user_id=current_user.id, recipe_id=recipe_id).first()
    if fav: db.session.delete(fav)
    else: db.session.add(Favorite(user_id=current_user.id, recipe_id=recipe_id))
    db.session.commit()
    return redirect(request.referrer or url_for('recipe_detail', recipe_id=recipe_id))

@app.route("/favorites")
@login_required
def favorites():
    user_favs = Favorite.query.filter_by(user_id=current_user.id).all()
    recipes = [f.recipe for f in user_favs]
    return render_template('favorites.html', recipes=recipes)

@app.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_admin: abort(403)
    return render_template('admin_users.html', users=User.query.all())

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Category.query.first():
            cat_list = sorted(["Vorspeise", "Hauptspeise", "Dessert", "Frühstück", "Snack", "Vegan", "Vegetarisch", "Backen", "Getränke", "Salate", "Suppen", "Pasta & Nudeln", "Fleisch", "Fisch", "Schnelle Küche", "Asiatisch", "Italienisch", "Mediterran", "Aufläufe", "Eintöpfe", "Saucen & Dips", "Fingerfood", "Low Carb", "Gesund & Fit", "Meeresfrüchte"])
            for name in cat_list: db.session.add(Category(name=name))
            db.session.commit()
    app.run(debug=True)