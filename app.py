import os
from datetime import datetime
from flask import Flask, render_template, url_for, flash, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'genussreise_geheimnis_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///genussreise.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Datenbank Modelle ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    recipes = db.relationship('Recipe', backref='author', lazy=True)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    prep_time = db.Column(db.Integer)
    servings = db.Column(db.Integer)
    calories = db.Column(db.Integer)
    protein = db.Column(db.Float)
    carbs = db.Column(db.Float)
    fat = db.Column(db.Float)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='recipe', lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    author = db.relationship('User', backref='my_comments', lazy=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_categories():
    categories_list = [
        "Abendessen", "Asiatisch", "Backen", "Beilagen", "Brot & Brötchen", 
        "Dessert", "Eintöpfe", "Fisch", "Fleisch", "Frühstück", 
        "Geflügel", "Getränke", "Hauptspeise", "Italienisch", "Low Carb", 
        "Mittagessen", "Nachtisch", "Pasta", "Pizza", "Salate", 
        "Snacks", "Suppen", "Vegan", "Vegetarisch", "Vorspeise"
    ]
    return [{'id': i+1, 'name': cat} for i, cat in enumerate(categories_list)]

# --- Routen ---

@app.route("/")
def index():
    page = request.args.get('page', 1, type=int)
    recipes = Recipe.query.order_by(Recipe.id.desc()).paginate(page=page, per_page=6)
    return render_template('index.html', recipes=recipes, all_categories=get_categories())

@app.route("/profile")
@login_required
def profile():
    recipes = Recipe.query.filter_by(author=current_user).all()
    return render_template('profile.html', recipes=recipes, user=current_user, all_categories=get_categories())

@app.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Nur für Administratoren zugänglich.', 'danger')
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('admin_users.html', users=users, all_categories=get_categories())

@app.route("/category/<int:category_id>")
def recipes_in_category(category_id):
    page = request.args.get('page', 1, type=int)
    recipes = Recipe.query.paginate(page=page, per_page=6)
    return render_template('index.html', recipes=recipes, all_categories=get_categories())

@app.route("/recipe/<int:recipe_id>", methods=['GET', 'POST'])
def recipe_detail(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if request.method == 'POST' and current_user.is_authenticated:
        comment = Comment(content=request.form['content'], rating=int(request.form['rating']), author=current_user, recipe=recipe)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('recipe_detail', recipe_id=recipe.id))
    
    avg_rating = db.session.query(db.func.avg(Comment.rating)).filter(Comment.recipe_id == recipe_id).scalar()
    return render_template('recipe_detail.html', recipe=recipe, avg_rating=round(avg_rating, 1) if avg_rating else None, all_categories=get_categories())

@app.route("/favorites")
@login_required
def favorites():
    flash('Favoriten-Funktion folgt bald!', 'info')
    return redirect(url_for('index'))

@app.route("/forgot_password")
def forgot_password():
    flash('Passwort-Wiederherstellung folgt.', 'info')
    return redirect(url_for('login'))

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        is_first = User.query.count() == 0
        user = User(username=request.form['username'], email=request.form['email'], password=hashed_pw, is_admin=is_first)
        db.session.add(user)
        db.session.commit()
        flash('Konto erstellt!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login fehlgeschlagen.', 'danger')
    return render_template('login.html')

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route("/recipe/new", methods=['GET', 'POST'])
@login_required
def new_recipe():
    if request.method == 'POST':
        recipe = Recipe(
            name=request.form['name'],
            instructions=request.form['instructions'],
            prep_time=request.form['prep_time'],
            servings=request.form['servings'],
            calories=request.form['calories'],
            protein=request.form['protein'],
            carbs=request.form['carbs'],
            fat=request.form['fat'],
            author=current_user
        )
        db.session.add(recipe)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('new_recipe.html', all_categories=get_categories())

@app.route("/admin/delete_user/<int:user_id>", methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('Benutzer gelöscht.', 'info')
    return redirect(url_for('admin_users'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)