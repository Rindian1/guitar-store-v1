# Guitar Store Search Feature Implementation Plan

## 1. Database Structure

### Products Table
```sql
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    description TEXT,
    image_url TEXT,
    stock INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Sample Data
```sql
INSERT INTO products (name, category, price, description, image_url, stock)
VALUES 
    ('Fender Stratocaster', 'Electric', 799.99, 'Classic electric guitar with versatile tone', '/static/images/stratocaster.jpg', 10),
    ('Gibson Les Paul', 'Electric', 1299.99, 'Iconic solid-body electric guitar', '/static/images/lespaul.jpg', 5),
    ('Martin D-28', 'Acoustic', 2499.99, 'Premium acoustic guitar with rich tone', '/static/images/d28.jpg', 8),
    ('Fender Precision Bass', 'Bass', 899.99, 'Legendary bass guitar', '/static/images/pbass.jpg', 7);
```

## 2. Backend Implementation (app.py)

### Imports
```python
from flask import Flask, render_template, request, redirect, url_for, g, jsonify
import sqlite3
import os
from datetime import datetime
```

### Database Setup
```python
def init_db():
    db = get_db()
    # Products table
    db.execute('''
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
    ''')
    db.commit()
```

### Search Route
```python
@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').lower()
    
    db = get_db()
    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if query:
        sql += " AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ?)"
        search_term = f"%{query.lower()}%"
        params.extend([search_term, search_term])
        
    if category:
        sql += " AND LOWER(category) = ?"
        params.append(category)
    
    # Add sorting
    sort_by = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')
    valid_sort_columns = ['name', 'price', 'created_at']
    
    if sort_by in valid_sort_columns:
        sql += f" ORDER BY {sort_by} {sort_order.upper()}"
    
    products = db.execute(sql, params).fetchall()
    
    # Get unique categories for filter dropdown
    categories = db.execute("SELECT DISTINCT category FROM products").fetchall()
    
    return render_template('search.html', 
                         products=products, 
                         search_query=query,
                         selected_category=category,
                         categories=categories,
                         sort_by=sort_by,
                         sort_order=sort_order)
```

## 3. Frontend Implementation

### Search Form (templates/search.html)
```html
{% extends "base.html" %}

{% block content %}
<div class="search-container">
    <form method="get" action="{{ url_for('search') }}" class="search-form">
        <input type="text" 
               name="q" 
               value="{{ search_query }}" 
               placeholder="Search guitars..." 
               class="search-input">
               
        <select name="category" class="category-select">
            <option value="">All Categories</option>
            {% for cat in categories %}
            <option value="{{ cat['category'] }}" 
                    {% if selected_category == cat['category'].lower() %}selected{% endif %}>
                {{ cat['category'] }}
            </option>
            {% endfor %}
        </select>
        
        <button type="submit" class="search-button">Search</button>
    </form>
    
    <div class="sort-options">
        <span>Sort by:</span>
        <a href="{{ url_for('search', q=search_query, category=selected_category, sort='name', order='asc') }}" 
           class="{% if sort_by == 'name' and sort_order == 'asc' %}active{% endif %}">
            Name (A-Z)
        </a>
        <a href="{{ url_for('search', q=search_query, category=selected_category, sort='price', order='asc') }}" 
           class="{% if sort_by == 'price' and sort_order == 'asc' %}active{% endif %}">
            Price (Low-High)
        </a>
        <a href="{{ url_for('search', q=search_query, category=selected_category, sort='price', order='desc') }}" 
           class="{% if sort_by == 'price' and sort_order == 'desc' %}active{% endif %}">
            Price (High-Low)
        </a>
    </div>
</div>

<div class="products-grid">
    {% for product in products %}
    <div class="product-card">
        <img src="{{ product['image_url'] or url_for('static', filename='images/placeholder.jpg') }}" 
             alt="{{ product['name'] }}"
             class="product-image">
        <div class="product-info">
            <h3 class="product-name">{{ product['name'] }}</h3>
            <p class="product-category">{{ product['category'] }}</p>
            <p class="product-price">${{ "%.2f"|format(product['price']) }}</p>
            {% if product['stock'] > 0 %}
                <p class="in-stock">In Stock ({{ product['stock'] }})</p>
                <button class="add-to-cart" data-product-id="{{ product['id'] }}">
                    Add to Cart
                </button>
            {% else %}
                <p class="out-of-stock">Out of Stock</p>
            {% endif %}
        </div>
    </div>
    {% else %}
    <div class="no-results">
        <p>No products found. Try adjusting your search.</p>
    </div>
    {% endfor %}
</div>
{% endblock %}
```

## 4. CSS Styling (static/css/search.css)

```css
/* Search Form */
.search-container {
    max-width: 1200px;
    margin: 20px auto;
    padding: 0 15px;
}

.search-form {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
}

.search-input {
    flex: 1;
    padding: 10px 15px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 16px;
}

.category-select {
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: white;
}

.search-button {
    padding: 10px 20px;
    background-color: #e67e50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.3s;
}

.search-button:hover {
    background-color: #d86f45;
}

/* Sort Options */
.sort-options {
    margin: 15px 0;
    padding: 10px 0;
    border-bottom: 1px solid #eee;
}

.sort-options a {
    margin-right: 15px;
    color: #666;
    text-decoration: none;
}

.sort-options a.active {
    color: #e67e50;
    font-weight: bold;
}

/* Products Grid */
.products-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 20px;
    padding: 20px 0;
}

.product-card {
    border: 1px solid #eee;
    border-radius: 8px;
    overflow: hidden;
    transition: transform 0.3s, box-shadow 0.3s;
}

.product-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
}

.product-image {
    width: 100%;
    height: 200px;
    object-fit: cover;
}

.product-info {
    padding: 15px;
}

.product-name {
    margin: 0 0 5px 0;
    font-size: 1.1em;
}

.product-category {
    color: #666;
    margin: 0 0 10px 0;
    font-size: 0.9em;
}

.product-price {
    font-weight: bold;
    color: #e67e50;
    font-size: 1.2em;
    margin: 10px 0;
}

.add-to-cart {
    width: 100%;
    padding: 8px;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.3s;
}

.add-to-cart:hover {
    background-color: #45a049;
}

.in-stock {
    color: #4CAF50;
    margin: 5px 0;
}

.out-of-stock {
    color: #f44336;
    margin: 5px 0;
}

.no-results {
    grid-column: 1 / -1;
    text-align: center;
    padding: 40px 0;
    color: #666;
}

/* Responsive Design */
@media (max-width: 768px) {
    .search-form {
        flex-direction: column;
    }
    
    .products-grid {
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    }
}
```

## 5. JavaScript for Live Search (Optional)

Add this to your base template or a separate JS file:

```javascript
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.querySelector('.search-input');
    const categorySelect = document.querySelector('.category-select');
    const productsGrid = document.querySelector('.products-grid');
    
    // Debounce function to limit API calls
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // Function to update search results
    function updateSearchResults() {
        const query = searchInput.value;
        const category = categorySelect.value;
        
        // Build URL with query parameters
        const url = new URL(window.location.origin + '/search');
        if (query) url.searchParams.append('q', query);
        if (category) url.searchParams.append('category', category);
        
        // Fetch and update results
        fetch(url)
            .then(response => response.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newProductsGrid = doc.querySelector('.products-grid');
                if (newProductsGrid) {
                    productsGrid.innerHTML = newProductsGrid.innerHTML;
                }
            })
            .catch(error => console.error('Error:', error));
    }
    
    // Add event listeners with debounce
    searchInput.addEventListener('input', debounce(updateSearchResults, 300));
    categorySelect.addEventListener('change', updateSearchResults);
    
    // Handle add to cart
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('add-to-cart')) {
            const productId = e.target.dataset.productId;
            // Add to cart logic here
            console.log('Add to cart:', productId);
            // You can implement cart functionality here
        }
    });
});
```

## 6. Implementation Steps

1. **Database Setup**:
   - Add the products table to your database
   - Insert sample guitar products

2. **Backend Updates**:
   - Add the search route to `app.py`
   - Ensure proper error handling

3. **Frontend Updates**:
   - Create `search.html` template
   - Add CSS for styling
   - Include the JavaScript for enhanced UX

4. **Testing**:
   - Test search functionality
   - Verify category filtering
   - Check sorting options
   - Test responsive design

5. **Deployment**:
   - Deploy database changes
   - Update production server
   - Test in production environment

## 7. Future Enhancements

1. **Advanced Search**:
   - Price range filters
   - Multiple category selection
   - Rating filters

2. **Performance**:
   - Add pagination
   - Implement caching
   - Optimize database queries

3. **User Experience**:
   - Add loading indicators
   - Implement infinite scroll
   - Add product quick view

4. **Features**:
   - Save search preferences
   - Recently viewed products
   - Product comparison

This implementation provides a solid foundation for your guitar store's search functionality that can be extended as your needs grow.
