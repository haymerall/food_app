import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_dance.contrib.google import make_google_blueprint, google
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_secret")

# --- SQLAlchemy config ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasty.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, User  # import after app config
db.init_app(app)

# Google OAuth setup
google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    redirect_to="home"
)
app.register_blueprint(google_bp, url_prefix="/login")

# --- demo data (replace with DB-backed models later) ---
restaurants = [
    {"id": 1, "name": "Pizza Palace", "menu": [
        {"id": 1, "name": "Margherita Pizza", "price": 10},
        {"id": 2, "name": "Pepperoni Pizza", "price": 12}
    ]},
    {"id": 2, "name": "Burger Barn", "menu": [
        {"id": 1, "name": "Classic Burger", "price": 8},
        {"id": 2, "name": "Cheese Burger", "price": 9}
    ]}
]
orders = []

# helper: load google user into session if available
@app.before_request
def load_google_user():
    if session.get('user'):
        return
    try:
        if google.authorized:
            resp = google.get("/oauth2/v2/userinfo")
            if resp.ok:
                info = resp.json()
                session['user'] = info.get('email')
    except Exception:
        pass

@app.route('/')
def home():
    return render_template('index.html', restaurants=restaurants, user=session.get('user'))

@app.route('/restaurant/<int:rest_id>')
def restaurant(rest_id):
    rest = next((r for r in restaurants if r['id'] == rest_id), None)
    if not rest:
        return "Restaurant not found", 404
    return render_template('restaurant.html', restaurant=rest, user=session.get('user'))

@app.route('/order', methods=['POST'])
def order():
    if not session.get('user'):
        flash('Please log in to place an order.', 'warning')
        return redirect(url_for('login'))
    try:
        rest_id = int(request.form.get('restaurant_id', ''))
        item_id = int(request.form.get('item_id', ''))
    except (ValueError, TypeError):
        flash('Invalid order data.', 'danger')
        return redirect(url_for('home'))

    rest = next((r for r in restaurants if r['id'] == rest_id), None)
    if not rest:
        flash('Restaurant not found.', 'danger')
        return redirect(url_for('home'))
    item = next((i for i in rest['menu'] if i['id'] == item_id), None)
    if not item:
        flash('Menu item not found.', 'danger')
        return redirect(url_for('restaurant', rest_id=rest_id))

    orders.append({"restaurant": rest['name'], "item": item['name'], "user": session.get('user')})
    flash(f'Order placed: {item["name"]} from {rest["name"]}', 'success')
    return redirect(url_for('orders_view'))

@app.route('/orders')
def orders_view():
    user_orders = [o for o in orders if o.get("user") == session.get('user')]
    return render_template('orders.html', orders=user_orders, user=session.get('user'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not email or not password:
            flash('Please fill all fields.', 'warning')
            return redirect(url_for('signup'))

        with app.app_context():
            existing = User.query.filter_by(email=email).first()
            if existing:
                flash('Email already registered. Please log in.', 'warning')
                return redirect(url_for('login'))

            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

        session['user'] = email
        flash('Signup successful! You are now logged in.', 'success')
        return redirect(url_for('home'))
    return render_template('signup.html', user=session.get('user'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        with app.app_context():
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                session['user'] = email
                flash('Logged in successfully.', 'success')
                return redirect(url_for('home'))
        flash('Invalid credentials. Please try again.', 'danger')
        return redirect(url_for('login'))
    return render_template('login.html', user=session.get('user'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# Ensure DB tables exist on app start and run server
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
# ...existing code...