from flask import Flask, jsonify, request, render_template
import os
import braintree
import sqlite3
from sqlite3 import Error

app = Flask(__name__)

# ===== Config from ENV =====
BRAINTREE_ENV = os.getenv("BRAINTREE_ENV", "Sandbox")  # "Sandbox" or "Production"
MERCHANT_ID = os.getenv("BRAINTREE_MERCHANT_ID")
PUBLIC_KEY = os.getenv("BRAINTREE_PUBLIC_KEY")
PRIVATE_KEY = os.getenv("BRAINTREE_PRIVATE_KEY")
# optional plan id (create plan in Braintree dashboard if you want subscriptions)
DEFAULT_PLAN_ID = os.getenv("BRAINTREE_PLAN_ID", "")

# ===== Braintree Gateway =====
env = braintree.Environment.Sandbox if BRAINTREE_ENV.lower() == "sandbox" else braintree.Environment.Production
gateway = braintree.BraintreeGateway(
    braintree.Configuration(
        env,
        merchant_id=MERCHANT_ID,
        public_key=PUBLIC_KEY,
        private_key=PRIVATE_KEY
    )
)

# ===== Simple SQLite DB (optional) =====
DB_FILE = "data.db"

def create_connection(db_file=DB_FILE):
    try:
        conn = sqlite3.connect(db_file, check_same_thread=False)
        return conn
    except Error as e:
        print(e)
    return None

conn = create_connection()
# create table if not exists
with conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nonce TEXT,
        customer_id TEXT,
        payment_method_token TEXT,
        transaction_id TEXT,
        subscription_id TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

# ===== Routes =====
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/client_token", methods=["GET"])
def client_token():
    # If you want to generate client token for a particular customer:
    # client_token = gateway.client_token.generate({"customer_id": "existing_customer_id"})
    client_token = gateway.client_token.generate()
    return jsonify({"clientToken": client_token})

@app.route("/vault", methods=["POST"])
def vault():
    """
    Expected JSON:
    {
      "payment_method_nonce": "...",
      "customer": {"first_name":"Saad","last_name":"Test","email":"a@b.com"},
      "create_transaction": true,
      "amount": "1.00"
    }
    """
    data = request.get_json() or {}
    nonce = data.get("payment_method_nonce")
    customer = data.get("customer", {})
    create_transaction = data.get("create_transaction", False)
    amount = data.get("amount")

    if not nonce:
        return jsonify({"success": False, "error": "payment_method_nonce required"}), 400

    # create customer (optional)
    result_cust = gateway.customer.create({
        "first_name": customer.get("first_name", "Test"),
        "last_name": customer.get("last_name", "User"),
        "email": customer.get("email", "")
    })

    if not result_cust.is_success:
        return jsonify({"success": False, "error": result_cust.message}), 400

    customer_id = result_cust.customer.id

    # vault payment method
    pm_result = gateway.payment_method.create({
        "customer_id": customer_id,
        "payment_method_nonce": nonce,
        "options": {"make_default": True, "verify_card": False}
    })

    if not pm_result.is_success:
        return jsonify({"success": False, "error": pm_result.message}), 400

    pm_token = pm_result.payment_method.token

    response = {"success": True, "customer_id": customer_id, "payment_method_token": pm_token}

    # optionally create sale
    if create_transaction and amount:
        sale_result = gateway.transaction.sale({
            "amount": amount,
            "payment_method_token": pm_token,
            "options": {"submit_for_settlement": True}
        })
        if sale_result.is_success:
            response["transaction_id"] = sale_result.transaction.id
        else:
            response["sale_error"] = sale_result.message

    # save to sqlite
    with conn:
        conn.execute(
            "INSERT INTO payments (nonce, customer_id, payment_method_token, transaction_id) VALUES (?,?,?,?)",
            (nonce, customer_id, pm_token, response.get("transaction_id"))
        )

    return jsonify(response)

@app.route("/create_subscription", methods=["POST"])
def create_subscription():
    """
    JSON:
    {
      "payment_method_token": "...",
      "plan_id": "plan_123"
    }
    """
    data = request.get_json() or {}
    token = data.get("payment_method_token")
    plan_id = data.get("plan_id") or DEFAULT_PLAN_ID

    if not token or not plan_id:
        return jsonify({"success": False, "error": "payment_method_token and plan_id required"}), 400

    result = gateway.subscription.create({
        "payment_method_token": token,
        "plan_id": plan_id
    })

    if result.is_success:
        sub_id = result.subscription.id
        # store
        with conn:
            conn.execute("INSERT INTO payments (payment_method_token, subscription_id) VALUES (?,?)", (token, sub_id))
        return jsonify({"success": True, "subscription_id": sub_id})
    else:
        return jsonify({"success": False, "error": result.message}), 400

if __name__ == "__main__":
    # port 8080 for Railway compatibility
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
