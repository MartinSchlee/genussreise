# 1. Imports
import os
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import math

# 2. App-Initialisierung & Konfiguration
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SECRET_KEY'] = 'eine-sehr-geheime-zeichenkette'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static/uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['ADMIN_USERNAMES'] = ['Martin', 'Julia', 'Chefkoch']

# Datenbank- & Login-Setup
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# 3. Datenbank-Modelle
recipe_categories = db.Table('recipe_categories',
    db.Column('recipe_id', db.Integer, db.ForeignKey('recipe.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True)
)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    parent = db.relationship('Category', remote_side=[id], backref='children', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    recipes = db.relationship('Recipe', backref='author', lazy=True)
    ratings = db.relationship('Rating', backref='user', lazy=True)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    portions = db.Column(db.Integer, nullable=False, default=4)
    time_prep = db.Column(db.String(50))
    time_cook = db.Column(db.String(50))
    time_rest = db.Column(db.String(50))
    nutrition_kcal = db.Column(db.String(50))
    nutrition_protein = db.Column(db.String(50))
    nutrition_carbs = db.Column(db.String(50))
    nutrition_fat = db.Column(db.String(50))
    categories = db.relationship('Category', secondary=recipe_categories, lazy='subquery', backref=db.backref('recipes', lazy=True))
    ratings = db.relationship('Rating', backref='recipe', lazy=True, cascade="all, delete-orphan")

    @property
    def average_rating(self):
        if not self.ratings: return 0
        return sum(r.stars for r in self.ratings) / len(self.ratings)

    @property
    def rating_count(self):
        return len(self.ratings)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stars = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

# 4. Helferfunktionen und Routen
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def inject_categories():
    unsorted_categories = Category.query.filter_by(parent_id=None).all()
    desired_order = ['Rezepte', 'Backen', 'Sonstige']
    def sort_key(category):
        try: return desired_order.index(category.name)
        except ValueError: return len(desired_order)
    sorted_categories = sorted(unsorted_categories, key=sort_key)
    return dict(top_level_categories=sorted_categories)

@app.route('/')
def index():
    all_recipes = Recipe.query.order_by(Recipe.id.desc()).all()
    return render_template('index.html', recipes=all_recipes)

@app.route('/recipe/<int:recipe_id>')
def recipe_detail(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template('recipe_detail.html', recipe=recipe)

@app.route('/category/<int:category_id>')
def recipes_by_category(category_id):
    category = Category.query.get_or_404(category_id)
    recipes_in_category = category.recipes
    return render_template('recipes_by_category.html', category=category, recipes=recipes_in_category)

@app.route('/search')
def search():
    query = request.args.get('q')
    if not query: return redirect(url_for('index'))
    search_term = f"%{query}%"
    results = Recipe.query.filter(or_(Recipe.title.ilike(search_term), Recipe.ingredients.ilike(search_term), Recipe.instructions.ilike(search_term))).all()
    return render_template('search_results.html', query=query, recipes=results)

# DIESE ROUTE HAT GEFEHLT!
@app.route('/rate_recipe/<int:recipe_id>', methods=['POST'])
@login_required
def rate_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    stars = int(request.form.get('stars'))

    existing_rating = Rating.query.filter_by(user_id=current_user.id, recipe_id=recipe_id).first()
    
    if existing_rating:
        existing_rating.stars = stars
    else:
        new_rating = Rating(stars=stars, user_id=current_user.id, recipe_id=recipe_id)
        db.session.add(new_rating)
    
    db.session.commit()

    return jsonify({
        'success': True,
        'average_rating': recipe.average_rating,
        'rating_count': recipe.rating_count
    })

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Benutzername oder E-Mail existiert bereits.')
            return redirect(url_for('register'))
        new_user = User(username=username, email=email, password_hash=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash('Registrierung erfolgreich! Willkommen.', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Ungültiger Benutzername oder Passwort.')
            return redirect(url_for('login'))
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/create_recipe', methods=['GET', 'POST'])
@login_required
def create_recipe():
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        image_file = request.files.get('image')
        image_filename = 'default.jpg'
        if image_file and image_file.filename != '' and allowed_file(image_file.filename):
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        
        new_recipe = Recipe(
            title=request.form.get('title'),
            ingredients=request.form.get('ingredients'),
            instructions=request.form.get('instructions'),
            image_file=image_filename,
            author=current_user,
            portions=request.form.get('portions', type=int),
            time_prep=request.form.get('time_prep'),
            time_cook=request.form.get('time_cook'),
            time_rest=request.form.get('time_rest'),
            nutrition_kcal=request.form.get('nutrition_kcal'),
            nutrition_protein=request.form.get('nutrition_protein'),
            nutrition_carbs=request.form.get('nutrition_carbs'),
            nutrition_fat=request.form.get('nutrition_fat')
        )
        
        category_ids = request.form.getlist('categories')
        for cat_id in category_ids:
            category = Category.query.get(cat_id)
            if category:
                new_recipe.categories.append(category)

        db.session.add(new_recipe)
        db.session.commit()
        flash('Dein Rezept wurde erfolgreich erstellt!', 'success')
        return redirect(url_for('index'))
    
    return render_template('create_recipe.html', categories=categories)

@app.route('/delete_recipe/<int:recipe_id>', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    recipe_to_delete = Recipe.query.get_or_404(recipe_id)
    if not current_user.is_authenticated or current_user.username not in app.config['ADMIN_USERNAMES']:
        abort(403)
    if recipe_to_delete.image_file != 'default.jpg':
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], recipe_to_delete.image_file)
        if os.path.exists(image_path):
            os.remove(image_path)
    db.session.delete(recipe_to_delete)
    db.session.commit()
    flash('Das Rezept wurde erfolgreich gelöscht!', 'success')
    return redirect(url_for('index'))

@app.route('/edit_recipe/<int:recipe_id>', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    categories = Category.query.order_by(Category.name).all()

    if recipe.author != current_user:
        abort(403)
    if request.method == 'POST':
        recipe.title = request.form.get('title')
        recipe.ingredients = request.form.get('ingredients')
        recipe.instructions = request.form.get('instructions')
        recipe.portions = request.form.get('portions', type=int)
        recipe.time_prep = request.form.get('time_prep')
        recipe.time_cook = request.form.get('time_cook')
        recipe.time_rest = request.form.get('time_rest')
        recipe.nutrition_kcal = request.form.get('nutrition_kcal')
        recipe.nutrition_protein = request.form.get('nutrition_protein')
        recipe.nutrition_carbs = request.form.get('nutrition_carbs')
        recipe.nutrition_fat = request.form.get('nutrition_fat')
        
        new_image = request.files.get('image')
        if new_image and new_image.filename != '' and allowed_file(new_image.filename):
            if recipe.image_file != 'default.jpg':
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], recipe.image_file)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            new_filename = secure_filename(new_image.filename)
            new_image.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
            recipe.image_file = new_filename
        
        recipe.categories.clear()
        category_ids = request.form.getlist('categories')
        for cat_id in category_ids:
            category = Category.query.get(cat_id)
            if category:
                recipe.categories.append(category)

        db.session.commit()
        flash('Dein Rezept wurde aktualisiert!', 'success')
        return redirect(url_for('index'))
    
    return render_template('edit_recipe.html', recipe=recipe, categories=categories)

def create_initial_categories():
    if Category.query.first() is None:
        rezepte_cat = Category(name='Rezepte')
        backen_cat = Category(name='Backen')
        sonstige_cat = Category(name='Sonstige')
        
        db.session.add_all([rezepte_cat, backen_cat, sonstige_cat])
        db.session.commit()

        categories_structure = {
            rezepte_cat: ['Vorspeise', 'Hauptgericht', 'Dessert', 'Salat', 'Suppe', 'Fleisch', 'Fisch'],
            backen_cat: ['Kuchen', 'Brot', 'Gebäck'],
            sonstige_cat: ['Vegetarisch', 'Vegan', 'Schnell']
        }

        for parent_cat, child_names in categories_structure.items():
            for name in child_names:
                child_cat = Category(name=name, parent=parent_cat)
                db.session.add(child_cat)
        
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_initial_categories()
    app.run(debug=True, port=5000)
