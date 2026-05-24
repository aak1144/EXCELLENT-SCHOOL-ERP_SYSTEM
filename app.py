from flask import Flask, render_template, request, redirect, session, g, send_file, flash
import sqlite3
import datetime
import os
import pandas as pd
import openpyxl

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "school_erp_secure_key_2026"

DB = os.path.join(os.getcwd(), "school.db")


# ---------------- SAFE INTEGER ----------------
def safe_int(v):
    try:
        return int(v)
    except:
        return 0


# ---------------- DATABASE ----------------
def get_db():

    db = getattr(g, "_database", None)

    if db is None:
        db = g._database = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row

    return db


@app.teardown_appcontext
def close_db(exception):

    db = getattr(g, "_database", None)

    if db is not None:
        db.close()


# ---------------- INIT DATABASE ----------------
def init_db():

    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")

    c = db.cursor()

    # ADMINS
    c.execute("""
    CREATE TABLE IF NOT EXISTS admins(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    # STUDENTS
    c.execute("""
    CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admission TEXT,
        name TEXT,
        class TEXT,
        parent TEXT,
        phone TEXT,
        admission_fee INTEGER,
        tuition_fee INTEGER,
        bus_fee INTEGER,
        computer_fee INTEGER,
        other_fee INTEGER,
        total_fee INTEGER,
        paid INTEGER DEFAULT 0
    )
    """)

    # PAYMENTS
    c.execute("""
    CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt TEXT,
        student_id INTEGER,
        total_amount INTEGER,
        date TEXT
    )
    """)

    # EXPENSES
    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        amount INTEGER,
        category TEXT,
        date TEXT
    )
    """)

    # DEFAULT ADMIN
    if not c.execute("SELECT * FROM admins").fetchone():

        c.execute(
            "INSERT INTO admins VALUES(NULL,?,?)",
            ("admin", generate_password_hash("admin123"))
        )

    db.commit()
    db.close()


init_db()


# ---------------- RECEIPT NUMBER ----------------
def next_receipt():

    db = get_db()

    r = db.execute("SELECT MAX(id) FROM payments").fetchone()[0]

    r = 1 if r is None else r + 1

    return f"REC-{str(r).zfill(5)}"


# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        db = get_db()

        user = db.execute(
            "SELECT * FROM admins WHERE username=?",
            (request.form["username"],)
        ).fetchone()

        if user and check_password_hash(
            user["password"],
            request.form["password"]
        ):

            session["user"] = request.form["username"]

            return redirect("/dashboard")

    return render_template("login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    db = get_db()

    students = db.execute(
        "SELECT * FROM students"
    ).fetchall()

    collected = db.execute(
        "SELECT SUM(total_amount) t FROM payments"
    ).fetchone()["t"] or 0

    expenses = db.execute(
        "SELECT SUM(amount) t FROM expenses"
    ).fetchone()["t"] or 0

    pending = sum(
        safe_int(s["total_fee"]) - safe_int(s["paid"])
        for s in students
    )

    top_pending = db.execute("""
    SELECT *,
    (total_fee - paid) as due
    FROM students
    WHERE total_fee > paid
    ORDER BY due DESC
    LIMIT 3
    """).fetchall()

    top_expenses = db.execute("""
    SELECT *
    FROM expenses
    ORDER BY amount DESC
    LIMIT 3
    """).fetchall()

    return render_template(
        "dashboard.html",
        students=len(students),
        collected=collected,
        expenses=expenses,
        pending=pending,
        top_pending=top_pending,
        top_expenses=top_expenses
    )


# ---------------- STUDENTS ----------------
@app.route("/students", methods=["GET", "POST"])
def students():

    if "user" not in session:
        return redirect("/")

    db = get_db()

    if request.method == "POST":

        admission_fee = safe_int(request.form.get("admission_fee"))
        tuition_fee = safe_int(request.form.get("tuition_fee"))
        bus_fee = safe_int(request.form.get("bus_fee"))
        computer_fee = safe_int(request.form.get("computer_fee"))
        other_fee = safe_int(request.form.get("other_fee"))

        total = (
            admission_fee +
            tuition_fee +
            bus_fee +
            computer_fee +
            other_fee
        )

        db.execute("""
        INSERT INTO students
        (
            admission,name,class,parent,phone,
            admission_fee,tuition_fee,bus_fee,
            computer_fee,other_fee,total_fee
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            request.form["adm"],
            request.form["name"],
            request.form["class"],
            request.form["parent"],
            request.form["phone"],
            admission_fee,
            tuition_fee,
            bus_fee,
            computer_fee,
            other_fee,
            total
        ))

        db.commit()

        flash("Student Added Successfully!")

    data = db.execute("""
    SELECT *
    FROM students
    ORDER BY id DESC
    """).fetchall()

    return render_template(
        "students.html",
        students=data
    )


# ---------------- DELETE STUDENT ----------------
@app.route("/delete/<int:id>")
def delete_student(id):

    if "user" not in session:
        return redirect("/")

    db = get_db()

    db.execute(
        "DELETE FROM payments WHERE student_id=?",
        (id,)
    )

    db.execute(
        "DELETE FROM students WHERE id=?",
        (id,)
    )

    db.commit()

    flash("Student Deleted Successfully!")

    return redirect("/students")


# ---------------- EXPORT EXCEL ----------------
@app.route("/export_transactions")
def export_transactions():

    if "user" not in session:
        return redirect("/")

    db = get_db()

    data = db.execute("""
    SELECT students.name,
           students.class,
           payments.receipt,
           payments.total_amount,
           payments.date
    FROM payments
    JOIN students
    ON payments.student_id = students.id
    ORDER BY payments.id DESC
    """).fetchall()

    df = pd.DataFrame(data, columns=[
        "Student Name",
        "Class",
        "Receipt Number",
        "Amount Paid",
        "Date"
    ])

    filename = "transactions.xlsx"

    df.to_excel(filename, index=False)

    return send_file(
        filename,
        as_attachment=True
    )


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)