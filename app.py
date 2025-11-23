from flask import Flask
from flask import render_template
from flask import request, redirect, url_for
from flask import abort
import sqlite3
import os
from flask import g 
from flask import jsonify
import json
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email, EmailNotValidError

app = Flask(__name__, instance_relative_config=True)
app.secret_key = 'your-secret-key-change-in-production'

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# --- Database helpers ---
# Use instance folder for database (works regardless of parent folder name)
import os

# Ensure instance directory exists
os.makedirs(app.instance_path, exist_ok=True)

# Database will be stored in instance/cart.db
DB_PATH = os.path.join(app.instance_path, 'cart.db')
print(f"Using database at: {DB_PATH}")  # Helpful for debugging

def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_db', None)
    if db is not None:
        db.close()

def init_db():
    try:
        print(f"Initializing database at: {DB_PATH}")
        db = get_db()
        
        # Enable foreign key support
        db.execute('PRAGMA foreign_keys = ON')
        
        # Create tables with error handling
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                product_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # Add user_id column if it doesn't exist (for existing databases)
        cursor = db.cursor()
        cursor.execute("PRAGMA table_info(cart_items)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'user_id' not in columns:
            cursor.execute('ALTER TABLE cart_items ADD COLUMN user_id INTEGER')
        if 'product_id' not in columns:
            cursor.execute('ALTER TABLE cart_items ADD COLUMN product_id INTEGER')
        
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                image_url TEXT,
                stock INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.commit()
        print("Database initialized successfully")
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")
        raise

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user:
        return User(user['id'], user['username'], user['email'], user['password_hash'])
    return None

def seed_products():
    """Seed sample products if products table is empty."""
    db = get_db()
    count = db.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c']
    if count == 0:
        db.executemany(
            'INSERT INTO products (name, category, price, description, image_url, stock) VALUES (?, ?, ?, ?, ?, ?)',
            [
                (
                    'Fender Stratocaster',
                    'Electric',
                    799.99,
                    'Classic electric guitar with versatile tone',
                    None,
                    10,
                ),
                (
                    'Gibson Les Paul',
                    'Electric',
                    1299.99,
                    'Iconic solid-body electric guitar',
                    None,
                    5,
                ),
                (
                    'Martin D-28',
                    'Acoustic',
                    2499.99,
                    'Premium acoustic guitar with rich tone',
                    None,
                    8,
                ),
                (
                    'Fender Precision Bass',
                    'Bass',
                    899.99,
                    'Legendary bass guitar',
                    None,
                    7,
                ),
            ],
        )
        db.commit()

@app.before_request
def setup():
    init_db()
    seed_products()

# --- Routes ---
@app.route('/')
def home():
    db = get_db()
    if current_user.is_authenticated:
        items = db.execute('SELECT id, name, price FROM cart_items WHERE user_id = ? ORDER BY id DESC', (current_user.id,)).fetchall()
    else:
        items = []  # No cart items for non-authenticated users
    total = sum((row['price'] or 0) for row in items)
    return render_template('index.html', cart_items=items, cart_total=total)

@app.route('/page-2.html')
def page2():
    return render_template('page-2.html')

@app.route('/index.html')
def index():
    return home()

@app.route('/add-item', methods=['POST'])
@login_required
def add_item():
    name = request.form.get('name', '').strip()
    price_raw = request.form.get('price', '0').strip()
    try:
        price = float(price_raw)
    except ValueError:
        price = 0.0
    if name:
        db = get_db()
        db.execute('INSERT INTO cart_items (name, price, user_id) VALUES (?, ?, ?)', (name, price, current_user.id))
        db.commit()
    return redirect(url_for('home'))

@app.route('/remove-item/<int:item_id>', methods=['POST'])
@login_required
def remove_item(item_id: int):
    db = get_db()
    db.execute('DELETE FROM cart_items WHERE id = ? AND user_id = ?', (item_id, current_user.id))
    db.commit()
    return redirect(url_for('home'))

@app.route('/search')
def search():
    query = (request.args.get('q') or '').strip()
    category = (request.args.get('category') or '').strip().lower()

    db = get_db()
    sql = 'SELECT * FROM products WHERE 1=1'
    params = []

    if query:
        sql += ' AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ?)'
        term = f"%{query.lower()}%"
        params.extend([term, term])

    if category:
        sql += ' AND LOWER(category) = ?'
        params.append(category)

    sort_by = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')
    valid_sort_columns = ['name', 'price', 'created_at']
    if sort_by not in valid_sort_columns:
        sort_by = 'name'
    if sort_order.lower() not in ['asc', 'desc']:
        sort_order = 'asc'
    sql += f' ORDER BY {sort_by} {sort_order.upper()}'

    products = db.execute(sql, params).fetchall()
    categories = db.execute('SELECT DISTINCT category FROM products').fetchall()

    return render_template(
        'search.html',
        products=products,
        search_query=query,
        selected_category=category,
        categories=categories,
        sort_by=sort_by,
        sort_order=sort_order,
    )

@app.route('/product/<int:product_id>')
def product_detail(product_id: int):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        abort(404)

    detailed_description = (
        (product['description'] or 'No description available.') +
        ' This is a detailed overview of the instrument, its tone, build, and typical use cases.'
    )

    # Check if product is already in cart
    in_cart = False
    if current_user.is_authenticated:
        in_cart = db.execute('SELECT COUNT(*) AS count FROM cart_items WHERE name = ? AND user_id = ?', 
                           (product['name'], current_user.id)).fetchone()['count'] > 0

    # Get YouTube links if they exist
    youtube_links = []
    if 'youtube_links' in product.keys() and product['youtube_links']:
        try:
            youtube_links = json.loads(product['youtube_links'])
        except (json.JSONDecodeError, TypeError):
            youtube_links = []

    return render_template(
        'product_detail.html',
        product=product,
        detailed_description=detailed_description,
        youtube_links=youtube_links,
        in_cart=in_cart
    )

@app.route('/shopping-cart')
@login_required
def shopping_cart():
    db = get_db()
    items = db.execute('SELECT id, name, price FROM cart_items WHERE user_id = ? ORDER BY id DESC', (current_user.id,)).fetchall()
    total = sum((row['price'] or 0) for row in items)
    return render_template('shopping_cart.html', cart_items=items, cart_total=total)

@app.route('/add-to-cart', methods=['POST'])
@login_required
def add_to_cart():
    product_id = request.form.get('product_id')
    if not product_id:
        return jsonify({'success': False, 'error': 'Product ID is required'}), 400

    db = get_db()
    try:
        # Fetch the product details
        product = db.execute('SELECT name, price FROM products WHERE id = ?', (product_id,)).fetchone()
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        # Add to cart with user_id
        db.execute('INSERT INTO cart_items (name, price, user_id) VALUES (?, ?, ?)', 
                  (product['name'], product['price'], current_user.id))
        db.commit()
        return jsonify({'success': True, 'message': 'Added to cart'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    errors = []
    
    # Validation
    if not username or len(username) < 3:
        errors.append('Username must be at least 3 characters long')
    if not email:
        errors.append('Email is required')
    else:
        try:
            validate_email(email)
        except EmailNotValidError:
            errors.append('Please enter a valid email address')
    if not password or len(password) < 6:
        errors.append('Password must be at least 6 characters long')
    if password != confirm_password:
        errors.append('Passwords do not match')
    
    if errors:
        return render_template('register.html', errors=errors, username=username, email=email)
    
    db = get_db()
    
    # Check if username or email already exists
    existing_user = db.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
    if existing_user:
        errors.append('Username or email already exists')
        return render_template('register.html', errors=errors, username=username, email=email)
    
    # Create new user
    password_hash = generate_password_hash(password)
    db.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)', 
              (username, email, password_hash))
    db.commit()
    
    # Log the user in
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    login_user(User(user['id'], user['username'], user['email'], user['password_hash']))
    
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    username_or_email = request.form.get('username_or_email', '').strip()
    password = request.form.get('password', '')
    remember = request.form.get('remember') == 'on'
    
    if not username_or_email or not password:
        return render_template('login.html', error='Please enter username/email and password')
    
    db = get_db()
    
    # Find user by username or email
    user = db.execute('SELECT * FROM users WHERE username = ? OR email = ?', 
                     (username_or_email, username_or_email)).fetchone()
    
    if not user or not check_password_hash(user['password_hash'], password):
        return render_template('login.html', error='Invalid username/email or password')
    
    # Update last login
    db.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
    db.commit()
    
    # Log the user in
    login_user(User(user['id'], user['username'], user['email'], user['password_hash']), remember=remember)
    
    return redirect(url_for('home'))

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)