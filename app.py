import os
import uuid
from datetime import datetime
from flask import Flask, render_template, url_for, flash, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'genussreise_geheimnis_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///genussreise.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Bitte melde dich an, um diese Seite zu sehen."
login_manager.login_message_category = "info"

# --- Datenbank Modelle ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    recipes = db.relationship('Recipe', backref='author', lazy=True)
    favorites = db.relationship('Favorite', backref='user', lazy=True, cascade="all, delete-orphan")

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.String(50))
    name = db.Column(db.String(100), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

# NEU: Favoriten-Tabelle
class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    prep_time = db.Column(db.Integer, default=0)
    cook_time = db.Column(db.Integer, default=0)
    rest_time = db.Column(db.Integer, default=0)
    servings = db.Column(db.Integer, default=1)
    calories = db.Column(db.Integer, default=0) 
    protein = db.Column(db.Float, default=0.0)
    carbs = db.Column(db.Float, default=0.0)
    fat = db.Column(db.Float, default=0.0)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ingredients = db.relationship('Ingredient', backref='recipe', lazy=True, cascade="all, delete-orphan")
    favorites = db.relationship('Favorite', backref='recipe', lazy=True, cascade="all, delete-orphan")

    @property
    def total_time(self):
        return (self.prep_time or 0) + (self.cook_time or 0) + (self.rest_time or 0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_categories():
    cat_names = ["Abendessen", "Asiatisch", "Backen", "Beilagen", "Brot & Brötchen", "Dessert", 
                 "Eintöpfe", "Fisch", "Fleisch", "Frühstück", "Geflügel", "Getränke", 
                 "Hauptspeise", "Italienisch", "Low Carb", "Mittagessen", "Nachtisch", 
                 "Pasta", "Pizza", "Salate", "Snacks", "Suppen", "Vegan", "Vegetarisch", "Vorspeise"]
    return [{'id': i+1, 'name': name} for i, name in enumerate(cat_names)]

@app.context_processor
def inject_categories():
    return dict(all_categories=get_categories())

# --- Routen ---

@app.route("/")
def index():
    page = request.args.get('page', 1, type=int)
    recipes = Recipe.query.order_by(Recipe.id.desc()).paginate(page=page, per_page=6)
    return render_template('index.html', recipes=recipes)

@app.route("/category/<int:category_id>")
def recipes_in_category(category_id):
    page = request.args.get('page', 1, type=int)
    recipes = Recipe.query.paginate(page=page, per_page=6)
    return render_template('index.html', recipes=recipes)

@app.route("/recipe/new", methods=['GET', 'POST'])
@login_required
def new_recipe():
    if request.method == 'POST':
        filename = 'default.jpg'
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                unique_filename = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                filename = unique_filename
        
        recipe = Recipe(
            name=request.form.get('name'),
            instructions=request.form.get('instructions', ''),
            prep_time=int(request.form.get('prep_time', 0) or 0),
            cook_time=int(request.form.get('cook_time', 0) or 0),
            rest_time=int(request.form.get('rest_time', 0) or 0),
            servings=int(request.form.get('servings', 1) or 1),
            calories=int(request.form.get('calories', 0) or 0),
            protein=float(request.form.get('protein', 0.0) or 0.0),
            carbs=float(request.form.get('carbs', 0.0) or 0.0),
            fat=float(request.form.get('fat', 0.0) or 0.0),
            image_file=filename,
            author=current_user
        )
        db.session.add(recipe)
        db.session.flush()
        
        amounts = request.form.getlist('ing_amount[]')
        names = request.form.getlist('ing_name[]')
        for amount, ing_name in zip(amounts, names):
            if ing_name.strip():
                new_ing = Ingredient(amount=amount, name=ing_name, recipe=recipe)
                db.session.add(new_ing)
        db.session.commit()
        flash('Rezept erstellt!', 'success')
        return redirect(url_for('index'))
    return render_template('new_recipe.html')

@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    # Prüfen, ob das Rezept vom aktuellen Nutzer favorisiert wurde
    is_favorited = False
    if current_user.is_authenticated:
        fav = Favorite.query.filter_by(user_id=current_user.id, recipe_id=recipe.id).first()
        is_favorited = fav is not None
    return render_template('recipe_detail.html', recipe=recipe, is_favorited=is_favorited)

# NEU: Route zum Umschalten (Hinzufügen/Entfernen) eines Favoriten
@app.route("/recipe/<int:recipe_id>/toggle_favorite", methods=['POST'])
@login_required
def toggle_favorite(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    favorite = Favorite.query.filter_by(user_id=current_user.id, recipe_id=recipe.id).first()
    
    if favorite:
        db.session.delete(favorite)
        flash('Rezept aus Favoriten entfernt.', 'info')
    else:
        new_favorite = Favorite(user_id=current_user.id, recipe_id=recipe.id)
        db.session.add(new_favorite)
        flash('Rezept zu Favoriten hinzugefügt!', 'success')
        
    db.session.commit()
    return redirect(request.referrer or url_for('recipe_detail', recipe_id=recipe.id))

@app.route("/recipe/<int:recipe_id>/edit", methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.author != current_user:
        flash('Keine Berechtigung!', 'danger')
        return redirect(url_for('recipe_detail', recipe_id=recipe.id))
    
    if request.method == 'POST':
        recipe.name = request.form.get('name')
        recipe.instructions = request.form.get('instructions')
        recipe.prep_time = int(request.form.get('prep_time', 0) or 0)
        recipe.cook_time = int(request.form.get('cook_time', 0) or 0)
        recipe.rest_time = int(request.form.get('rest_time', 0) or 0)
        recipe.servings = int(request.form.get('servings', 1) or 1)
        recipe.calories = int(request.form.get('calories', 0) or 0)
        recipe.protein = float(request.form.get('protein', 0.0) or 0.0)
        recipe.carbs = float(request.form.get('carbs', 0.0) or 0.0)
        recipe.fat = float(request.form.get('fat', 0.0) or 0.0)
        
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                unique_filename = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                recipe.image_file = unique_filename

        Ingredient.query.filter_by(recipe_id=recipe.id).delete()
        amounts = request.form.getlist('ing_amount[]')
        names = request.form.getlist('ing_name[]')
        for amount, ing_name in zip(amounts, names):
            if ing_name.strip():
                new_ing = Ingredient(amount=amount, name=ing_name, recipe=recipe)
                db.session.add(new_ing)
        
        db.session.commit()
        flash('Rezept aktualisiert!', 'success')
        return redirect(url_for('recipe_detail', recipe_id=recipe.id))
    return render_template('edit_recipe.html', recipe=recipe)

@app.route("/recipe/<int:recipe_id>/delete", methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.author != current_user:
        flash('Keine Berechtigung.', 'danger')
        return redirect(url_for('index'))
    db.session.delete(recipe)
    db.session.commit()
    flash('Rezept gelöscht.', 'success')
    return redirect(url_for('index'))

@app.route("/profile")
@login_required
def profile():
    recipes = Recipe.query.filter_by(author=current_user).all()
    all_users = User.query.all() if current_user.is_admin else []
    return render_template('profile.html', recipes=recipes, user=current_user, users=all_users)

# NEU: Die echte Favoriten-Route
@app.route("/favorites")
@login_required
def favorites():
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    # Hole alle Rezepte aus den Favoriten des Nutzers
    fav_recipes = [fav.recipe for fav in favs]
    return render_template('favorites.html', recipes=fav_recipes)

@app.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route("/admin/delete_user/<int:user_id>", methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('Benutzer erfolgreich gelöscht.', 'info')
    return redirect(request.referrer or url_for('admin_users'))

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        existing = User.query.filter_by(email=request.form['email']).first()
        if existing:
            flash('Email existiert bereits.', 'danger')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        is_first = (User.query.count() == 0)
        user = User(username=request.form['username'], email=request.form['email'], 
                    password=hashed_pw, is_admin=is_first)
        db.session.add(user)
        db.session.commit()
        flash('Erfolgreich registriert!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash('Login fehlgeschlagen.', 'danger')
    return render_template('login.html')

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route("/forgot_password")
def forgot_password():
    flash('Funktion folgt!', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)