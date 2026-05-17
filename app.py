from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "secret123"

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def create_users_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# Home Page Route
@app.route("/", methods=["GET"])
def home():
    city = request.args.get("city")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")

    query = "SELECT * FROM properties WHERE status='approved'"
    params = []

    if city:
        query += " AND city LIKE ?"
        params.append(f"%{city}%")

    if min_price:
        query += " AND price >= ?"
        params.append(min_price)

    if max_price:
        query += " AND price <= ?"
        params.append(max_price)

    conn = get_db()
    properties = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "home.html",
        properties=properties,
        city=city,
        min_price=min_price,
        max_price=max_price
    )


# register the users form
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, password, "agent")
        )
        conn.commit()
        conn.close()

        return redirect(url_for("home"))

    return render_template("register.html")
# Create login route
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]

            # 🔑 ROLE BASED REDIRECT
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            elif user["role"] == "agent":
                return redirect(url_for("agent_dashboard"))

            else:
                # normal user
                return redirect(url_for("dashboard"))

        else:
            error = "Invalid email or password"

    return render_template("login.html", error=error)

# Create dashboard route
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html")

# Logout route
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
# Create properties table
def create_properties_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            price TEXT,
            city TEXT,
            purpose TEXT,
            description TEXT
        )
    """)
    conn.commit()
    conn.close()
# Add Property route

from werkzeug.utils import secure_filename
#  add property
@app.route("/property/add", methods=["GET", "POST"])
def add_property():
    if "role" not in session or session["role"] != "agent":
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        city = request.form["city"]
        price = request.form["price"]
        purpose = request.form["purpose"]
        description = request.form["description"]

        image = request.files["image"]   # <-- from form

        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        conn = get_db()
        conn.execute("""
            INSERT INTO properties
            (title, city, price, purpose, description, image, user_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            title, city, price, purpose, description, filename, session["user_id"]
        ))
        conn.commit()
        conn.close()

        return redirect(url_for("agent_properties"))

    return render_template("add_property.html")


# Create “My Properties” page

@app.route("/my-properties")
def my_properties():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    properties = conn.execute(
        "SELECT * FROM properties WHERE user_id = ?",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return render_template("my_properties.html", properties=properties)

# Property Detail Route
@app.route("/property/<int:property_id>")
def property_detail(property_id):
    conn = get_db()
    property = conn.execute(
        "SELECT * FROM properties WHERE id = ?",
        (property_id,)
    ).fetchone()
    conn.close()

    if not property:
        return "Property not found", 404

    return render_template("property_detail.html", property=property)
# messages table
def create_messages_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            property_id INTEGER,
            message TEXT
        )
    """)
    conn.commit()
    conn.close()
# Message send route
@app.route("/message/<int:property_id>", methods=["GET", "POST"])
def send_message(property_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    property = conn.execute(
        "SELECT * FROM properties WHERE id = ?",
        (property_id,)
    ).fetchone()

    if not property:
        conn.close()
        return "Property not found", 404

    if request.method == "POST":
        message = request.form["message"]

        conn.execute("""
            INSERT INTO messages (sender_id, receiver_id, property_id, message)
            VALUES (?, ?, ?, ?)
        """, (
            session["user_id"],
            property["user_id"],
            property_id,
            message
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("home"))

    conn.close()
    return render_template("send_message.html", property=property)
# Owner Inbox (View Messages)

@app.route("/messages")
def messages():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    messages = conn.execute("""
        SELECT messages.*, properties.title
        FROM messages
        JOIN properties ON messages.property_id = properties.id
        WHERE messages.receiver_id = ?
        ORDER BY messages.id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template("messages.html", messages=messages)
# function to add role column
def add_role_column():
    conn = get_db()
    try:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT")
        conn.commit()
    except:
        pass
    conn.close()
    # default role for existing users
def set_default_roles():
    conn = get_db()
    conn.execute("""
        UPDATE users
        SET role = 'user'
        WHERE role IS NULL
    """)
    conn.commit()
    conn.close()
# Create ONE Admin User

def create_admin_user():
    conn = get_db()

    admin_exists = conn.execute(
        "SELECT * FROM users WHERE role = 'admin'"
    ).fetchone()

    if not admin_exists:
        conn.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
        """, ("Admin", "admin@example.com", "admin123", "admin"))

        conn.commit()

    conn.close()
# Create Admin Login Route

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        admin = conn.execute("""
            SELECT * FROM users
            WHERE email = ? AND password = ? AND role = 'admin'
        """, (email, password)).fetchone()
        conn.close()

        if admin:
            session["user_id"] = admin["id"]
            session["user_name"] = admin["name"]
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))
        else:
            error = "Invalid admin credentials"

    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

# Admin Dashboard Route
@app.route("/admin/dashboard")
def admin_dashboard():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("admin_login"))

    conn = get_db()

    total_properties = conn.execute(
        "SELECT COUNT(*) FROM properties"
    ).fetchone()[0]

    pending_properties = conn.execute(
        "SELECT COUNT(*) FROM properties WHERE status = 'pending'"
    ).fetchone()[0]

    approved_properties = conn.execute(
        "SELECT COUNT(*) FROM properties WHERE status = 'approved'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_properties=total_properties,
        pending_properties=pending_properties,
        approved_properties=approved_properties
    )
def add_status_column():
    conn = get_db()
    try:
        conn.execute("ALTER TABLE properties ADD COLUMN status TEXT")
        conn.commit()
    except:
        pass
    conn.close()

def set_default_property_status():
    conn = get_db()
    conn.execute("""
        UPDATE properties
        SET status = 'pending'
        WHERE status IS NULL
    """)
    conn.commit()
    conn.close()

# pending properties
@app.route("/admin/properties/pending")
def admin_pending_properties():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("admin_login"))

    conn = get_db()
    properties = conn.execute(
        "SELECT * FROM properties WHERE status = 'pending'"
    ).fetchall()
    conn.close()

    return render_template("admin_pending_properties.html", properties=properties)
# Approve Property Route
@app.route("/admin/property/approve/<int:property_id>")
def approve_property(property_id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("admin_login"))

    conn = get_db()
    conn.execute(
        "UPDATE properties SET status = 'approved' WHERE id = ?",
        (property_id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("admin_pending_properties"))

# Reject Property Route
@app.route("/admin/property/reject/<int:property_id>")
def reject_property(property_id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("admin_login"))

    conn = get_db()
    conn.execute(
        "UPDATE properties SET status = 'rejected' WHERE id = ?",
        (property_id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("admin_pending_properties"))

# admin all properties 

@app.route("/admin/properties")
def admin_all_properties():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("admin_login"))

    conn = get_db()
    properties = conn.execute("""
        SELECT properties.*, users.name AS agent_name
        FROM properties
        JOIN users ON properties.user_id = users.id
        ORDER BY properties.id DESC
    """).fetchall()
    conn.close()

    return render_template(
        "admin_all_properties.html",
        properties=properties
    )
# admin see agent 

@app.route("/admin/agents")
def admin_agents():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("admin_login"))

    conn = get_db()

    agents = conn.execute("""
        SELECT 
            users.id,
            users.name,
            users.email,
            COUNT(properties.id) AS total_properties,
            SUM(CASE WHEN properties.status = 'pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN properties.status = 'approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN properties.status = 'rejected' THEN 1 ELSE 0 END) AS rejected
        FROM users
        LEFT JOIN properties ON users.id = properties.user_id
        WHERE users.role = 'agent'
        GROUP BY users.id
    """).fetchall()

    conn.close()

    return render_template("admin_agents.html", agents=agents)

# AGENT DASHBOARD ROUTE

@app.route("/agent/dashboard")
def agent_dashboard():
    if "role" not in session or session["role"] != "agent":
        return redirect(url_for("login"))

    conn = get_db()

    stats = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected
        FROM properties
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    conn.close()

    return render_template(
        "agent_dashboard.html",
        stats=stats
    )

# (Agent Properties + Status)

@app.route("/agent/properties")
def agent_properties():
    if "role" not in session or session["role"] != "agent":
        return redirect(url_for("login"))

    conn = get_db()
    properties = conn.execute("""
        SELECT 
            id,
            title,
            city,
            price,
            status,
            image
        FROM properties
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template(
        "agent_properties.html",
        properties=properties
    )

# add image column

def add_image_column():
    conn = get_db()
    try:
        conn.execute("ALTER TABLE properties ADD COLUMN image TEXT")
        conn.commit()
    except:
        pass
    conn.close()

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# add image for old property adde before image placeholder 

@app.route("/agent/property/<int:property_id>/image", methods=["POST"])
def upload_property_image(property_id):
    if "role" not in session or session["role"] != "agent":
        return redirect(url_for("login"))

    image = request.files["image"]
    filename = secure_filename(image.filename)
    image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    conn = get_db()
    conn.execute("""
        UPDATE properties
        SET image = ?
        WHERE id = ? AND user_id = ?
    """, (filename, property_id, session["user_id"]))
    conn.commit()
    conn.close()

    return redirect(url_for("agent_properties"))
# admin upload route
@app.route("/admin/property/<int:property_id>/image", methods=["POST"])
def admin_upload_property_image(property_id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("admin_login"))

    image = request.files.get("image")
    if not image:
        return redirect(url_for("admin_all_properties"))

    filename = secure_filename(image.filename)
    image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    conn = get_db()
    conn.execute(
        "UPDATE properties SET image = ? WHERE id = ?",
        (filename, property_id)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("admin_all_properties"))

# Edit Property
@app.route("/property/edit/<int:property_id>", methods=["GET", "POST"])
def edit_property(property_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    property = conn.execute(
        "SELECT * FROM properties WHERE id=? AND user_id=?",
        (property_id, session["user_id"])
    ).fetchone()

    if not property:
        conn.close()
        return "Property not found or access denied"

    if request.method == "POST":
        title = request.form["title"]
        price = request.form["price"]
        city = request.form["city"]
        purpose = request.form["purpose"]
        description = request.form["description"]

        conn.execute("""
            UPDATE properties
            SET title=?, price=?, city=?, purpose=?, description=?
            WHERE id=? AND user_id=?
        """, (title, price, city, purpose, description, property_id, session["user_id"]))

        conn.commit()
        conn.close()
        return redirect("/my-properties")

    conn.close()
    return render_template("edit_property.html", property=property)
# delete property route
@app.route("/property/delete/<int:property_id>")
def delete_property(property_id):
    # user must be logged in
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    property = conn.execute(
        "SELECT * FROM properties WHERE id = ?",
        (property_id,)
    ).fetchone()

    # security: only owner can delete
    if not property or property["user_id"] != session["user_id"]:
        conn.close()
        return "Unauthorized", 403

    # delete image file if exists
    if property["image"]:
        image_path = os.path.join(app.root_path, "static/uploads", property["image"])
        if os.path.exists(image_path):
            os.remove(image_path)

    # delete property record
    conn.execute(
        "DELETE FROM properties WHERE id = ?",
        (property_id,)
    )
    conn.commit()
    conn.close()

    return redirect("/my-properties")


if __name__ == "__main__":
    create_users_table()
    create_properties_table()
    create_messages_table()
    add_role_column()
    set_default_roles()
    add_status_column()
    set_default_property_status()
    create_admin_user()
    add_image_column()
app.run(debug=True)






