from flask import Flask
from flask import render_template
from flask import request, redirect, url_for
import sqlite3
import os
from flask import g 
from flask import jsonify

app = Flask(__name__, instance_relative_config=True)

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
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                image_url TEXT,
                product_url TEXT,
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

def seed_products():
    """Seed sample products if products table is empty."""
    db = get_db()
    count = db.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c']
    if count == 0:
        db.executemany(
            'INSERT INTO products (name, category, price, description, image_url, product_url, stock) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                (
                    'Fender Stratocaster',
                    'Electric',
                    799.99,
                    'Classic electric guitar with versatile tone',
                    None,
                    'https://www.fender.com/start',
                    10,
                ),
                (
                    'Gibson Les Paul',
                    'Electric',
                    1299.99,
                    'Iconic solid-body electric guitar',
                    None,
                    'https://www.gibson.com/',
                    5,
                ),
                (
                    'Martin D-28',
                    'Acoustic',
                    2499.99,
                    'Premium acoustic guitar with rich tone',
                    None,
                    'https://www.martinguitar.com/',
                    8,
                ),
                (
                    'Fender Precision Bass',
                    'Bass',
                    899.99,
                    'Legendary bass guitar',
                    None,
                    'https://www.fender.com/start',
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
    items = db.execute('SELECT id, name, price FROM cart_items ORDER BY id DESC').fetchall()
    total = sum((row['price'] or 0) for row in items)
    return render_template('index.html', cart_items=items, cart_total=total)

@app.route('/page-2.html')
def page2():
    return render_template('page-2.html')

@app.route('/index.html')
def index():
    return home()

@app.route('/add-item', methods=['POST'])
def add_item():
    name = request.form.get('name', '').strip()
    price_raw = request.form.get('price', '0').strip()
    try:
        price = float(price_raw)
    except ValueError:
        price = 0.0
    if name:
        db = get_db()
        db.execute('INSERT INTO cart_items (name, price) VALUES (?, ?)', (name, price))
        db.commit()
    return redirect(url_for('home'))

@app.route('/remove-item/<int:item_id>', methods=['POST'])
def remove_item(item_id: int):
    db = get_db()
    db.execute('DELETE FROM cart_items WHERE id = ?', (item_id,))
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

@app.route('/shopping-cart')
def shopping_cart():
    db = get_db()
    items = db.execute('SELECT id, name, price FROM cart_items ORDER BY id DESC').fetchall()
    total = sum((row['price'] or 0) for row in items)
    return render_template('shopping_cart.html', cart_items=items, cart_total=total)

@app.route('/add-to-cart', methods=['POST'])
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

        # Add to cart
        db.execute('INSERT INTO cart_items (name, price) VALUES (?, ?)', 
                  (product['name'], product['price']))
        db.commit()
        return jsonify({'success': True, 'message': 'Added to cart'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)