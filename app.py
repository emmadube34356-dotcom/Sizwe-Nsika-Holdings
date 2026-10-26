import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g

app = Flask(__name__)
app.secret_key = 'sizwe_nsika_secret_key_change_in_production'
DATABASE = 'database.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Business settings table
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS business_info
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY,
                           name
                           TEXT,
                           tagline
                           TEXT,
                           phone
                           TEXT,
                           whatsapp
                           TEXT,
                           email
                           TEXT,
                           region
                           TEXT
                       )
                       ''')

        # Pricing configuration table
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS pricing_config
                       (
                           service_key
                           TEXT
                           PRIMARY
                           KEY,
                           service_name
                           TEXT,
                           base_price
                           REAL,
                           rate_per_sqm
                           REAL
                       )
                       ''')

        # Transport & Global rates
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS transport_config
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY,
                           base_transport_fee
                           REAL,
                           rate_per_km
                           REAL
                       )
                       ''')

        # Insert defaults if empty
        cursor.execute('SELECT COUNT(*) FROM business_info')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                           INSERT INTO business_info (id, name, tagline, phone, whatsapp, email, region)
                           VALUES (1, 'Sizwe Nsika Holdings (Pty) Ltd', 'BUILDING TOMORROW TOGETHER',
                                   '067 234 0388', '27672340388', 'info@sizwensikaholdings.co.za',
                                   'Serving South Africa & The SADC Region')
                           ''')

        cursor.execute('SELECT COUNT(*) FROM transport_config')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO transport_config (id, base_transport_fee, rate_per_km) VALUES (1, 350.0, 12.5)')

        cursor.execute('SELECT COUNT(*) FROM pricing_config')
        if cursor.fetchone()[0] == 0:
            services = [
                ('construction', 'Construction', 500.0, 450.0),
                ('electrical', 'Electrical Installation', 300.0, 150.0),
                ('plumbing', 'Plumbing Services', 350.0, 180.0),
                ('aluminium', 'Aluminium Windows & Doors', 400.0, 380.0),
                ('glass', 'Glass Supply & Installation', 250.0, 320.0),
                ('folding_doors', 'Folding Stacking Doors', 600.0, 650.0),
                ('partitioning', 'Office / Home Partitioning', 350.0, 220.0),
                ('patio', 'Patio Enclosures', 550.0, 480.0),
                ('garage', 'Garage Doors', 800.0, 250.0),
                ('security_gates', 'Expandable Security Gates', 450.0, 280.0),
                ('burglar_proofing', 'Burglar Proofing', 300.0, 200.0)
            ]
            cursor.executemany('INSERT INTO pricing_config VALUES (?, ?, ?, ?)', services)

        db.commit()


# Context processor for global business variables
@app.context_processor
def inject_business_info():
    db = get_db()
    info = db.execute('SELECT * FROM business_info WHERE id = 1').fetchone()
    return dict(biz=info)


# Routes
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/services')
def services():
    db = get_db()
    services_list = db.execute('SELECT * FROM pricing_config').fetchall()
    return render_template('services.html', services=services_list)


@app.route('/gallery')
def gallery():
    return render_template('gallery.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash('Thank you for contacting Sizwe Nsika Holdings! We will respond shortly.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')


@app.route('/quote', methods=['GET', 'POST'])
def quote():
    db = get_db()
    services_list = db.execute('SELECT * FROM pricing_config').fetchall()
    transport = db.execute('SELECT * FROM transport_config WHERE id = 1').fetchone()

    quote_result = None
    if request.method == 'POST':
        service_key = request.form.get('service')
        height_cm = float(request.form.get('height', 0))
        width_cm = float(request.form.get('width', 0))
        distance_km = float(request.form.get('distance', 0))

        area_sqm = (height_cm / 100.0) * (width_cm / 100.0)
        svc = db.execute('SELECT * FROM pricing_config WHERE service_key = ?', (service_key,)).fetchone()

        if svc:
            material_cost = svc['base_price'] + (area_sqm * svc['rate_per_sqm'])
            transport_cost = transport['base_transport_fee'] + (distance_km * transport['rate_per_km'])
            total_est = material_cost + transport_cost

            quote_result = {
                'service_name': svc['service_name'],
                'height_cm': height_cm,
                'width_cm': width_cm,
                'area_sqm': round(area_sqm, 2),
                'distance_km': distance_km,
                'material_cost': round(material_cost, 2),
                'transport_cost': round(transport_cost, 2),
                'total_est': round(total_est, 2)
            }

    return render_template('quote.html', services=services_list, quote=quote_result)


# Admin Portal
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'sizwe123':
            session['admin_logged_in'] = True
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid admin credentials.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_business':
            db.execute('''
                       UPDATE business_info
                       SET name=?,
                           tagline=?,
                           phone=?,
                           whatsapp=?,
                           email=?,
                           region=?
                       WHERE id = 1
                       ''', (
                           request.form.get('name'), request.form.get('tagline'),
                           request.form.get('phone'), request.form.get('whatsapp'),
                           request.form.get('email'), request.form.get('region')
                       ))
            db.commit()
            flash('Business settings updated!', 'success')

        elif action == 'update_pricing':
            service_key = request.form.get('service_key')
            base_price = float(request.form.get('base_price', 0))
            rate_per_sqm = float(request.form.get('rate_per_sqm', 0))
            db.execute('''
                       UPDATE pricing_config
                       SET base_price=?,
                           rate_per_sqm=?
                       WHERE service_key = ?
                       ''', (base_price, rate_per_sqm, service_key))
            db.commit()
            flash('Service pricing updated!', 'success')

        elif action == 'update_transport':
            base_fee = float(request.form.get('base_transport_fee', 0))
            rate_km = float(request.form.get('rate_per_km', 0))
            db.execute('''
                       UPDATE transport_config
                       SET base_transport_fee=?,
                           rate_per_km=?
                       WHERE id = 1
                       ''', (base_fee, rate_km))
            db.commit()
            flash('Transport rates updated!', 'success')

    services_list = db.execute('SELECT * FROM pricing_config').fetchall()
    transport = db.execute('SELECT * FROM transport_config WHERE id = 1').fetchone()
    biz = db.execute('SELECT * FROM business_info WHERE id = 1').fetchone()

    return render_template('admin.html', services=services_list, transport=transport, biz=biz)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
    if __name__ == '__main__':
        init_db()
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)