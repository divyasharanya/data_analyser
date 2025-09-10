import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

# --- App Initialization ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
CORS(app)

# --- Frontend Route (Serve HTML files) ---
@app.route('/', defaults={'path': 'mainpage.html'})
@app.route('/<path:path>')
def serve_file(path):
    file_path = os.path.join(BASE_DIR, path)
    if os.path.exists(file_path) and path.endswith('.html'):
        return send_from_directory(BASE_DIR, path)
    abort(404)

# --- Database Configuration ---
DB_USER = "avnadmin"
DB_PASS = "YOURPASS"
DB_HOST = "HOST"
DB_PORT = "14586"
DB_NAME = "defaultdb"

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "created_at": self.created_at.isoformat()
        }

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), db.ForeignKey('users.username'), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(10,2), nullable=False)
    week_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "category": self.category,
            "amount": float(self.amount),
            "week_date": self.week_date.isoformat(),
            "created_at": self.created_at.isoformat()
        }

# --- API Routes ---

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required"}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "Username already exists"}), 409

    hashed_password = generate_password_hash(data["password"])
    user = User(username=data["username"], password=hashed_password)

    try:
        db.session.add(user)
        db.session.commit()
        return jsonify({"message": "User created successfully"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Username and password are required"}), 400

    user = User.query.filter_by(username=data['username']).first()
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({"error": "Invalid username or password"}), 401

    return jsonify({"message": "Login successful", "user": user.to_dict()}), 200

@app.route('/api/add_expense', methods=['POST'])
def add_expense():
    data = request.get_json()
    required_fields = ['username', 'category', 'amount', 'week_date']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    if not User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "User not found"}), 404

    try:
        week_date = datetime.strptime(data['week_date'], '%Y-%m-%d').date()
        expense = Expense(
            username=data['username'],
            category=data['category'],
            amount=data['amount'],
            week_date=week_date
        )
        db.session.add(expense)
        db.session.commit()
        return jsonify({"message": "Expense added successfully", "expense": expense.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to add expense: {str(e)}"}), 500

@app.route('/api/get_expenses/<string:username>', methods=['GET'])
def get_expenses(username):
    if not User.query.filter_by(username=username).first():
        return jsonify({"error": "User not found"}), 404

    expenses = Expense.query.filter_by(username=username).order_by(Expense.week_date.desc()).all()
    return jsonify({
        "username": username,
        "expenses": [e.to_dict() for e in expenses],
        "total_expenses": len(expenses)
    }), 200

@app.route('/api/weekly_summary/<string:username>', methods=['GET'])
def weekly_summary(username):
    if not User.query.filter_by(username=username).first():
        return jsonify({"error": "User not found"}), 404

    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    expenses = Expense.query.filter(
        Expense.username == username,
        Expense.week_date >= start_of_week,
        Expense.week_date <= end_of_week
    ).all()

    if not expenses:
        return jsonify({
            "username": username,
            "period": f"{start_of_week} to {end_of_week}",
            "message": "No expenses found for the current week."
        }), 200

    summary = {}
    total = 0
    for e in expenses:
        summary[e.category] = summary.get(e.category, 0) + float(e.amount)
        total += float(e.amount)

    highest_category = max(summary, key=summary.get) if summary else None

    return jsonify({
        "username": username,
        "period": f"{start_of_week} to {end_of_week}",
        "category_summary": summary,
        "total_amount": total,
        "highest_category": {
            "category": highest_category,
            "amount": summary.get(highest_category)
        } if highest_category else None,
        "expense_count": len(expenses)
    }), 200

@app.route('/api/expenses/<int:expense_id>', methods=['PUT'])
def update_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    data = request.get_json()

    if 'category' in data:
        expense.category = data['category']
    if 'amount' in data:
        expense.amount = data['amount']
    if 'week_date' in data:
        expense.week_date = datetime.strptime(data['week_date'], '%Y-%m-%d').date()

    try:
        db.session.commit()
        return jsonify({"message": "Expense updated successfully", "expense": expense.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update expense: {str(e)}"}), 500

@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    try:
        db.session.delete(expense)
        db.session.commit()
        return jsonify({"message": "Expense deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete expense: {str(e)}"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        print("Initializing database...")
        db.create_all()
        print("Database initialized successfully.")
    app.run(host='0.0.0.0', port=5003, debug=True)
