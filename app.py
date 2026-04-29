import os
import datetime
import re
from datetime import timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from markupsafe import escape, Markup
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from flask_mail import Mail, Message

# --- 1. Konfiguration ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SECRET_KEY'] = 'dein_sehr_geheimer_schlüssel_hier'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
app.config['ADMIN_USERNAMES'] = ['Martin', 'Daniel'] 
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'fasi270669@gmail.com'
app.config['MAIL_PASSWORD'] = 'wlqs fbtg fqqi uywd'
app.config['MAIL_DEFAULT_SENDER'] = ('Genussreise', 'fasi270669@gmail.com')

db = SQLAlchemy(app)
mail = Mail(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])


# --- 2. Datenbankmodelle --- (NACH OBEN VERSCHOBEN)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    recipes = db.relationship('Recipe', backref='author', lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship('Review', backref='reviewer', lazy=True, cascade="all, delete-orphan")

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    recipes = db.relationship('Recipe', backref='category', lazy=True)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    prep_time = db.Column(db.String(50), nullable=True)
    cook_time = db.Column(db.String(50), nullable=True)
    rest_time = db.Column(db.String(50), nullable=True)
    total_time = db.Column(db.String(50), nullable=True)
    servings = db.Column(db.String(50), nullable=True)
    calories = db.Column(db.String(50), nullable=True)
    protein = db.Column(db.String(50), nullable=True)
    carbs = db.Column(db.String(50), nullable=True)
    fat = db.Column(db.String(50), nullable=True)
    rating_sum = db.Column(db.Integer, default=0)
    rating_count = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    ingredients = db.relationship('Ingredient', backref='recipe', lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship('Review', backref='recipe', lazy=True, cascade="all, delete-orphan")

    @property
    def average_rating(self):
        if self.rating_count == 0: return 0
        return round(self.rating_sum / self.rating_count, 1)

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(50), nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)


# --- 3. Login Manager & Hilfsfunktionen ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_global_variables():
    # Jetzt ist 'Category' definiert und dieser Aufruf ist gültig
    categories = Category.query.order_by(Category.name).all()
    return dict(config=app.config, all_categories=categories, current_year=datetime.datetime.now(timezone.utc).year)

@app.template_filter('nl2br')
def nl2br_filter(s):
    return escape(s).replace('\n', Markup('<br>'))

def is_password_strong(password):
    if len(password) < 10: return False, "Das Passwort muss mindestens 10 Zeichen lang sein."
    if not re.search(r"[a-z]", password): return False, "Das Passwort muss mindestens einen Kleinbuchstaben enthalten."
    if not re.search(r"[A-Z]", password): return False, "Das Passwort muss mindestens einen Großbuchstaben enthalten."
    if not re.search(r"[0-9]", password): return False, "Das Passwort muss mindestens eine Ziffer enthalten."
    if not re.search(r"[\W_]", password): return False, "Das Passwort muss mindestens ein Sonderzeichen enthalten (z.B. -, _, !, #)."
    return True, ""


# --- 4. Routen ---
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
        new_recipe = Recipe(name=request.form.get('recipe_name'), instructions=request.form.get('instructions'), prep_time=request.form.get('prep_time'), cook_time=request.form.get('cook_time'), rest_time=request.form.get('rest_time'), total_time=request.form.get('total_time'), servings=request.form.get('servings'), calories=request.form.get('calories'), protein=request.form.get('protein'), carbs=request.form.get('carbs'), fat=request.form.get('fat'), image_file='default.jpg', author=current_user, category_id=request.form.get('category_id'))
        if 'image_file' in request.files:
            image_file = request.files['image_file']
            if image_file.filename != '':
                image_filename = secure_filename(image_file.filename)
                image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                new_recipe.image_file = image_filename
        db.session.add(new_recipe)
        ingredient_names = request.form.getlist('ingredient_name[]')
        quantities = request.form.getlist('quantity[]')
        units = request.form.getlist('unit[]')
        for i in range(len(ingredient_names)):
            if ingredient_names[i]:
                db.session.add(Ingredient(name=ingredient_names[i], quantity=quantities[i], unit=units[i], recipe=new_recipe))
        db.session.commit()
        flash('Rezept erfolgreich hinzugefügt!', 'success')
        return redirect(url_for('index'))
    return render_template('add_recipe.html', categories=categories)

@app.route('/edit_recipe/<int:recipe_id>', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    categories = Category.query.order_by(Category.name).all()
    if recipe.author != current_user and current_user.username not in app.config['ADMIN_USERNAMES']:
        flash('Du hast keine Berechtigung, dieses Rezept zu bearbeiten.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        recipe.name, recipe.instructions, recipe.prep_time, recipe.cook_time, recipe.rest_time, recipe.total_time, recipe.servings, recipe.category_id, recipe.calories, recipe.protein, recipe.carbs, recipe.fat = request.form.get('recipe_name'), request.form.get('instructions'), request.form.get('prep_time'), request.form.get('cook_time'), request.form.get('rest_time'), request.form.get('total_time'), request.form.get('servings'), request.form.get('category_id'), request.form.get('calories'), request.form.get('protein'), request.form.get('carbs'), request.form.get('fat')
        Ingredient.query.filter_by(recipe_id=recipe.id).delete()
        ingredient_names = request.form.getlist('ingredient_name[]')
        quantities = request.form.getlist('quantity[]')
        units = request.form.getlist('unit[]')
        for i in range(len(ingredient_names)):
            if ingredient_names[i]:
                db.session.add(Ingredient(name=ingredient_names[i], quantity=quantities[i], unit=units[i], recipe=recipe))
        db.session.commit()
        flash('Rezept erfolgreich aktualisiert!', 'success')
        return redirect(url_for('recipe_detail', recipe_id=recipe.id))
    return render_template('edit_recipe.html', recipe=recipe, categories=categories)

@app.route('/delete_recipe/<int:recipe_id>', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if current_user.username not in app.config['ADMIN_USERNAMES']:
        flash('Nur Administratoren können Rezepte löschen.', 'danger')
        return redirect(url_for('recipe_detail', recipe_id=recipe.id))
    db.session.delete(recipe)
    db.session.commit()
    flash('Rezept wurde vom Administrator gelöscht.', 'success')
    return redirect(url_for('index'))

@app.route('/search')
def search():
    query = request.args.get('query')
    if not query:
        return redirect(url_for('index'))
    search_term = f"%{query}%"
    results = Recipe.query.filter(or_(Recipe.name.ilike(search_term), Recipe.instructions.ilike(search_term))).all()
    return render_template('search_results.html', recipes=results, query=query)

@app.route('/rate_recipe/<int:recipe_id>', methods=['POST'])
@login_required
def rate_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    rating, comment = int(request.form.get('rating')), request.form.get('comment')
    if Review.query.filter_by(reviewer=current_user, recipe=recipe).first():
        flash('Du hast dieses Rezept bereits bewertet.', 'warning')
        return redirect(url_for('recipe_detail', recipe_id=recipe_id))
    if 1 <= rating <= 5:
        db.session.add(Review(rating=rating, text=comment, reviewer=current_user, recipe=recipe))
        recipe.rating_sum += rating
        recipe.rating_count += 1
        db.session.commit()
        flash('Vielen Dank für deine Bewertung!', 'success')
    return redirect(url_for('recipe_detail', recipe_id=recipe_id))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user:
            token = s.dumps(user.email, salt='email-confirm')
            link = url_for('reset_password', token=token, _external=True)
            msg = Message('Dein Link zum Zurücksetzen des Passworts', recipients=[user.email])
            msg.body = f'Hallo {user.username},\n\nklicke auf den folgenden Link, um dein Passwort zurückzusetzen: {link}\n\nDein Genussreise-Team'
            try:
                mail.send(msg)
                flash('Ein Link zum Zurücksetzen des Passworts wurde an deine E-Mail-Adresse gesendet.', 'success')
            except Exception as e:
                flash(f'E-Mail konnte nicht gesendet werden. Fehler: {e}', 'danger')
        else:
            flash('Kein Benutzer mit dieser E-Mail-Adresse gefunden.', 'warning')
    return render_template('forgot_password.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        password = request.form.get('password')
        is_strong, message = is_password_strong(password)
        if not is_strong:
            flash(message, 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=request.form.get('username')).first():
            flash('Benutzername bereits vergeben.', 'danger')
            return redirect(url_for('register'))
        db.session.add(User(username=request.form.get('username'), email=request.form.get('email'), password=generate_password_hash(password, method='pbkdf2:sha256')))
        db.session.commit()
        flash('Dein Account wurde erstellt! Du kannst dich jetzt einloggen.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try: email = s.loads(token, salt='email-confirm', max_age=1800)
    except:
        flash('Der Link zum Zurücksetzen des Passworts ist ungültig oder abgelaufen.', 'danger')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password')
        is_strong, message = is_password_strong(password)
        if not is_strong:
            flash(message, 'danger')
            return render_template('reset_password.html', token=token)
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(password, method='pbkdf2:sha256')
            db.session.commit()
            flash('Dein Passwort wurde erfolgreich zurückgesetzt! Du kannst dich jetzt einloggen.', 'success')
            return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user, remember=True)
            return redirect(url_for('index'))
        flash('Login fehlgeschlagen. Überprüfe Benutzername und Passwort.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- 5. Serverstart & DB-Initialisierung ---
def init_db():
    with app.app_context():
        db.create_all()
        if not Category.query.first():
            db.session.add_all([Category(name=cat) for cat in ['Abendessen', 'Asiatisch', 'Auflauf', 'Backen', 'Dessert', 'Deutsch', 'Eintopf', 'Französisch', 'Frühstück', 'Gebäck', 'Getränke', 'Glutenfrei', 'Hauptgericht', 'Indisch', 'Italienisch', 'Kuchen', 'Low Carb', 'Mediterran', 'Mexikanisch', 'Mittagessen', 'Salat', 'Snack', 'Smoothie', 'Suppe', 'Vegan', 'Vegetarisch', 'Vorspeise']])
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
