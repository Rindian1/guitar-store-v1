from flask import Flask
from flask import render_template
from flask import request, redirect, url_for
from flask import abort
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

import json

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

    # Get YouTube videos from the database
    youtube_videos = []
    if 'youtube_links' in product and product['youtube_links']:
        try:
            print("\n" + "="*50)
            print(f"DEBUG: Processing product {product_id}")
            
            # Get the raw data
            raw_links = product['youtube_links']
            print(f"Raw data type: {type(raw_links)}")
            print(f"Raw data length: {len(str(raw_links))} characters")
            print(f"First 200 chars: {str(raw_links)[:200]}")
            
            # Try to parse the JSON data
            if isinstance(raw_links, str):
                try:
                    # First try direct JSON parse
                    youtube_videos = json.loads(raw_links)
                    print("Successfully parsed JSON directly")
                except json.JSONDecodeError as e1:
                    print(f"Direct JSON parse failed: {e1}")
                    try:
                        # Try fixing common JSON issues
                        fixed_json = raw_links.replace("'", '"')
                        youtube_videos = json.loads(fixed_json)
                        print("Successfully parsed JSON after fixing quotes")
                    except json.JSONDecodeError as e2:
                        print(f"Fixed JSON parse failed: {e2}")
                        # Try to extract URLs using regex as a last resort
                        print("Attempting to extract URLs with regex...")
                        import re
                        url_matches = re.findall(r'"url"\s*:\s*"(https?://[^"]+)"', raw_links)
                        title_matches = re.findall(r'"title"\s*:\s*"([^"]+)"', raw_links)
                        
                        youtube_videos = []
                        for i, (url, title) in enumerate(zip(url_matches, title_matches)):
                            if i >= 3:  # Limit to 3 videos
                                break
                            youtube_videos.append({
                                'title': title,
                                'url': url,
                                'channel': 'Unknown Channel',
                                'duration': 'N/A',
                                'published': 'N/A',
                                'views': 0
                            })
                        print(f"Extracted {len(youtube_videos)} videos using regex")
            
            # If we have a single video (dict), convert to list
            if isinstance(youtube_videos, dict):
                youtube_videos = [youtube_videos]
            
            # Process the videos
            if not isinstance(youtube_videos, list):
                print(f"ERROR: Expected list but got {type(youtube_videos)}")
                youtube_videos = []
            else:
                processed_videos = []
                for i, video in enumerate(youtube_videos[:3]):  # Limit to 3 videos
                    if not isinstance(video, dict):
                        print(f"Skipping invalid video entry at index {i}: {video}")
                        continue
                    
                    # Clean and validate video data
                    video_url = str(video.get('url', '')).strip()
                    if not video_url.startswith(('http://', 'https://')):
                        print(f"Skipping invalid URL: {video_url}")
                        continue
                    
                    video_data = {
                        'title': str(video.get('title', f'Video {i+1}')).strip(),
                        'url': video_url,
                        'channel': str(video.get('channel', 'Unknown Channel')).strip(),
                        'duration': str(video.get('duration', 'N/A')).strip(),
                        'published': str(video.get('published', 'N/A')).strip(),
                        'views': int(video.get('views', 0)) if str(video.get('views', '0')).isdigit() else 0
                    }
                    processed_videos.append(video_data)
                
                youtube_videos = processed_videos
            
            print(f"Successfully processed {len(youtube_videos)} videos")
            for i, video in enumerate(youtube_videos, 1):
                print(f"  Video {i}: {video.get('title')}")
                print(f"    URL: {video.get('url')}")
            
        except Exception as e:
            print(f"CRITICAL ERROR processing YouTube links: {str(e)}")
            import traceback
            traceback.print_exc()
            youtube_videos = []
    
    print("="*50 + "\n")
    
    # Debug output
    print(f"Product ID: {product_id}")
    print(f"YouTube links found: {len(youtube_videos)}")
    for i, video in enumerate(youtube_videos, 1):
        print(f"  Video {i}: {video.get('title', 'No title')} - {video.get('url', 'No URL')}")
        print(f"     Channel: {video.get('channel', 'N/A')}")
        print(f"     Duration: {video.get('duration', 'N/A')}")
        print(f"     Published: {video.get('published', 'N/A')}")
        print(f"     Views: {video.get('views', 'N/A')}")
    
    # For backward compatibility, keep the sound_tests variable
    sound_tests = [
        {
            'title': video.get('title', 'Sound Demo'),
            'url': video.get('url', '#')
        }
        for video in youtube_videos
    ]

    return render_template(
        'product_detail.html',
        product=product,
        detailed_description=detailed_description,
        sound_tests=sound_tests,
        youtube_videos=youtube_videos,
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
    app.run(host='0.0.0.0', port=5002, debug=True)