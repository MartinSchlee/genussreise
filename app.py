import os
import datetime # NEU
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from markupsafe import escape, Markup

# --- 1. Konfiguration ---
app = Flask(__name__)
# ... (deine Konfiguration bleibt gleich) ...
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SECRET_KEY'] = 'dein_sehr_geheimer_schlüssel_hier'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
app.config['ADMIN_USERNAMES'] = ['Martin'] 

db = SQLAlchemy(app)

@app.context_processor
def inject_global_variables():
    categories = Category.query.order_by(Category.name).all()
    # NEU: Die aktuelle Jahreszahl für alle Templates verfügbar machen
    return dict(
        config=app.config, 
        all_categories=categories,
        current_year=datetime.datetime.utcnow().year 
    )

@app.template_filter('nl2br')
def nl2br_filter(s):
    return escape(s).replace('\n', Markup('<br>'))

# --- 2. Datenbankmodelle ---
# ... (alle Modelle bleiben unverändert) ...
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    recipes = db.relationship('Recipe', backref='author', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    recipes = db.relationship('Recipe', backref='category', lazy=True)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    servings = db.Column(db.String(50), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    ingredients = db.relationship('Ingredient', backref='recipe', lazy=True, cascade="all, delete-orphan")

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(50), nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

# --- Login Manager ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- 3. Routen ---
# ... (alle Routen bleiben unverändert) ...
@app.route('/')
def index():
    recipes = Recipe.query.order_by(Recipe.id.desc()).all()
    return render_template('index.html', recipes=recipes)

@app.route('/category/<int:category_id>')
def recipes_in_category(category_id):
    category = Category.query.get_or_404(category_id)
    return render_template('category_view.html', category=category)

@app.route('/recipe/<int:recipe_id>')
def recipe_detail(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template('recipe_detail.html', recipe=recipe)

@app.route('/add_recipe', methods=['GET', 'POST'])
@login_required
def add_recipe():
    categories = Category.query.order_by(Category.name).all()
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        if not category_id:
            flash('Bitte wähle eine Kategorie aus.', 'danger')
            return render_template('add_recipe.html', categories=categories)

        image_filename = 'default.jpg'
        if 'image_file' in request.files:
            image_file = request.files['image_file']
            if image_file.filename != '':
                image_filename = secure_filename(image_file.filename)
                image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        new_recipe = Recipe(
            name=request.form.get('recipe_name'),
            instructions=request.form.get('instructions'),
            servings=request.form.get('servings'),
            image_file=image_filename,
            author=current_user,
            category_id=category_id
        )
        db.session.add(new_recipe)
        
        ingredient_names = request.form.getlist('ingredient_name[]')
        quantities = request.form.getlist('quantity[]')
        units = request.form.getlist('unit[]')
        for i in range(len(ingredient_names)):
            if ingredient_names[i]:
                ingredient = Ingredient(name=ingredient_names[i], quantity=quantities[i], unit=units[i], recipe=new_recipe)
                db.session.add(ingredient)
        
        db.session.commit()
        flash('Rezept erfolgreich hinzugefügt!', 'success')
        return redirect(url_for('index'))
    
    return render_template('add_recipe.html', categories=categories)

@app.route('/edit_recipe/<int:recipe_id>', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    categories = Category.query.order_by(Category.name).all()
    if recipe.author != current_user:
        flash('Du hast keine Berechtigung, dieses Rezept zu bearbeiten.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        recipe.name = request.form.get('recipe_name')
        recipe.instructions = request.form.get('instructions')
        recipe.servings = request.form.get('servings')
        recipe.category_id = request.form.get('category_id')
        db.session.commit()
        flash('Rezept erfolgreich aktualisiert!', 'success')
        return redirect(url_for('recipe_detail', recipe_id=recipe.id))
    
    return render_template('edit_recipe.html', recipe=recipe, categories=categories)

@app.route('/delete_recipe/<int:recipe_id>', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.author != current_user and current_user.username not in app.config['ADMIN_USERNAMES']:
        flash('Du hast keine Berechtigung, dieses Rezept zu löschen.', 'danger')
        return redirect(url_for('index'))
    db.session.delete(recipe)
    db.session.commit()
    flash('Rezept wurde gelöscht.', 'success')
    return redirect(url_for('index'))

@app.route('/search', methods=['POST'])
def search():
    flash("Die Suchfunktion ist noch nicht implementiert.", "info")
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user, remember=True)
            return redirect(url_for('index'))
        flash('Login fehlgeschlagen. Überprüfe Benutzername und Passwort.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user_exists = User.query.filter_by(username=request.form.get('username')).first()
        if user_exists:
            flash('Benutzername bereits vergeben.', 'danger')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
        new_user = User(username=request.form.get('username'), email=request.form.get('email'), password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Dein Account wurde erstellt! Du kannst dich jetzt einloggen.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- 4. Serverstart & DB-Initialisierung ---
def init_db():
    with app.app_context():
        db.create_all()
        if not Category.query.first():
            default_categories = ['Frühstück', 'Hauptgericht', 'Dessert', 'Salat', 'Suppe', 'Italienisch', 'Asiatisch', 'Snack', 'Vegan', 'Vegetarisch']
            for cat_name in default_categories:
                db.session.add(Category(name=cat_name))
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
