import os
import braintree
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import logging

app = Flask(__name__)

# Database Configuration
DATABASE_URL = "postgresql://postgres:QmnqFPPwcEiVVFJYgUCsOKGObfAaXIla@junction.proxy.rlwy.net:39653/railway"
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Braintree Configuration (Sandbox)
braintree.Configuration.configure(
    environment=braintree.Environment.Sandbox,  # أو Production للإنتاج
    merchant_id="jbhmd5zs833t2pmq",
    public_key="w7dzx8kwtq3syrjf", 
    private_key="f8c3f16ba0f537427ac61c522fb3c7a4"
)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BillingAgreement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_id = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, active, cancelled
    approval_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    activated_at = db.Column(db.DateTime)

class PaymentLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    billing_agreement_id = db.Column(db.Integer, db.ForeignKey('billing_agreement.id'), nullable=False)
    transaction_id = db.Column(db.String(100))
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20))  # success, failed, pending
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Routes
@app.route('/')
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Braintree Billing Agreement Test</title>
    <script src="https://js.braintreegateway.com/web/3.96.1/js/client.min.js"></script>
    <script src="https://js.braintreegateway.com/web/3.96.1/js/paypal-checkout.min.js"></script>
</head>
<body>
    <h1>🚀 Test Billing Agreement</h1>
    
    <div id="customer-form">
        <h3>Customer Info</h3>
        <input type="email" id="email" placeholder="Email" value="test@example.com">
        <input type="text" id="name" placeholder="Name" value="Test User">
        <button onclick="setupBillingAgreement()">Setup PayPal Billing Agreement</button>
    </div>

    <div id="result"></div>

    <script>
        async function setupBillingAgreement() {
            const email = document.getElementById('email').value;
            const name = document.getElementById('name').value;
            
            if (!email || !name) {
                alert('Please fill in all fields');
                return;
            }

            try {
                const response = await fetch('/setup-billing-agreement', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        email: email,
                        name: name
                    })
                });

                const data = await response.json();
                console.log('Response:', data);

                if (data.success) {
                    document.getElementById('result').innerHTML = `
                        <h3>✅ Billing Agreement Created!</h3>
                        <p><strong>Token ID:</strong> ${data.token_id}</p>
                        <p><a href="${data.approval_url}" target="_blank" style="background: #0070ba; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                           🔗 Approve PayPal Agreement
                        </a></p>
                        <small>After approval, come back and check status</small>
                    `;
                } else {
                    document.getElementById('result').innerHTML = `
                        <h3>❌ Error:</h3>
                        <p>${data.error}</p>
                    `;
                }
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('result').innerHTML = `<h3>❌ Request Failed</h3>`;
            }
        }
    </script>
</body>
</html>
    """)

@app.route('/setup-billing-agreement', methods=['POST'])
def setup_billing_agreement():
    try:
        data = request.get_json()
        email = data.get('email')
        name = data.get('name')
        
        if not email or not name:
            return jsonify({'success': False, 'error': 'Email and name required'})

        # إنشاء أو الحصول على المستخدم
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, name=name)
            db.session.add(user)
            db.session.commit()

        # إنشاء Billing Agreement عبر Braintree
        result = braintree.PaymentMethod.create({
            "customer_id": None,  # سنحتاج إنشاء customer أو استخدام guest checkout
            "payment_method_nonce": None,  # لن نحتاجه في حالة PayPal
            "options": {
                "paypal": {
                    "payee_email": email,
                    "order_id": f"order_{user.id}_{int(datetime.now().timestamp())}",
                    "custom_field": f"user_{user.id}",
                    "description": "Monthly Subscription"
                }
            }
        })

        # الطريقة الصحيحة لـ PayPal Billing Agreement
        # نستخدم PayPal Checkout مع vault=true
        
        # إنشاء client token للعميل
        client_token_result = braintree.ClientToken.generate({
            "customer_id": None,  # guest checkout
        })
        
        if not client_token_result.is_success:
            return jsonify({
                'success': False, 
                'error': f'Failed to generate client token: {client_token_result.message}'
            })

        # في الحقيقة، Braintree PayPal يحتاج معالجة مختلفة
        # سنحاكي الـ response المطلوب مثل ExpressVPN
        
        # إنشاء معرف مؤقت للـ agreement
        temp_token = f"BA-{user.id}{int(datetime.now().timestamp())}"
        
        # حفظ البيانات في قاعدة البيانات
        agreement = BillingAgreement(
            user_id=user.id,
            token_id=temp_token,
            status='pending',
            approval_url=f"https://www.paypal.com/agreements/approve?ba_token={temp_token}"
        )
        db.session.add(agreement)
        db.session.commit()

        return jsonify({
            'success': True,
            'token_id': temp_token,
            'approval_url': agreement.approval_url,
            'client_token': client_token_result.client_token
        })

    except Exception as e:
        app.logger.error(f"Error in setup_billing_agreement: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/approve-agreement/<token_id>')
def approve_agreement(token_id):
    """
    هذا الـ endpoint سيتم استدعاؤه بعد موافقة العميل على PayPal
    """
    try:
        agreement = BillingAgreement.query.filter_by(token_id=token_id).first()
        if not agreement:
            return jsonify({'success': False, 'error': 'Agreement not found'})
        
        # تحديث حالة الاتفاقية
        agreement.status = 'active'
        agreement.activated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Billing agreement activated successfully',
            'token_id': token_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/charge-agreement/<token_id>', methods=['POST'])
def charge_agreement(token_id):
    """
    استخدام الـ billing agreement للدفع المتكرر
    """
    try:
        data = request.get_json()
        amount = data.get('amount', 9.99)  # Default subscription amount
        
        agreement = BillingAgreement.query.filter_by(
            token_id=token_id, 
            status='active'
        ).first()
        
        if not agreement:
            return jsonify({'success': False, 'error': 'Active agreement not found'})
        
        # في الحقيقة، سنحتاج استخدام Braintree Transaction API
        # لكن هنا سنحاكي العملية
        
        # محاكاة عملية الدفع
        payment_log = PaymentLog(
            billing_agreement_id=agreement.id,
            transaction_id=f"TXN_{int(datetime.now().timestamp())}",
            amount=amount,
            status='success'  # في الحقيقة هذا سيأتي من Braintree
        )
        db.session.add(payment_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'transaction_id': payment_log.transaction_id,
            'amount': amount,
            'message': 'Payment processed successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/agreements')
def list_agreements():
    """
    عرض جميع الاتفاقيات (للتجربة)
    """
    agreements = db.session.query(
        BillingAgreement, User
    ).join(User).all()
    
    result = []
    for agreement, user in agreements:
        result.append({
            'token_id': agreement.token_id,
            'user_email': user.email,
            'user_name': user.name,
            'status': agreement.status,
            'created_at': agreement.created_at.isoformat(),
            'activated_at': agreement.activated_at.isoformat() if agreement.activated_at else None
        })
    
    return jsonify(result)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
