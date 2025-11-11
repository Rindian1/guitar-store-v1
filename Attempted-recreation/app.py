from flask import Flask 
from flask import render_template   
import sqlite3 
import os  
from flask import g


app = Flask(__name__)
DB_PATH = os.path.join(app.root_path, 'cart.db') 

@app.route('/remove-item/<int:item_id>', methods=['POST'])
def remove_item(item_id):
    db = get_db()
    db.execute('DELETE FROM cart_items WHERE id = ?', (item_id,))
    db.commit()
    return redirect(url_for('home'))

def get_db(): 
    db = getattr(g, '_db', None)
    if db is None: 
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db 

def init_db(): 
    db = get_db() 
    db.execute(
        """ 
CREATE TABLE IF NOT EXISTS cart_items ( 
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL DEFAULT 0);
        """
    ) 
    db.commit()

@app.before_request 
def setup(): 
    init_db() 


@app.route('/') 
def home():  
    db = get_db()  
    items = db.execute("SELECT * FROM cart_items ORDER BY id DESC").fetchall() 
    total = sum((row['price'] or 0) for row in items)
    return render_template('index.html', cart_items=items, cart_total=total)

if __name__ == '__main__':
    app.run(debug=True)