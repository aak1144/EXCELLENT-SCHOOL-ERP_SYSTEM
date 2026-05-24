from flask import Flask,render_template,request,redirect,session,g,send_file,flash
import sqlite3,datetime,shutil
from werkzeug.security import generate_password_hash,check_password_hash
import pandas as pd
import os
import webbrowser
import openpyxl

app = Flask(__name__)
app.secret_key="school_erp_secure_key_2026"
import os

DB = os.path.join(os.getcwd(), "school.db")


def safe_int(v):
    try: return int(v)
    except: return 0


def get_db():
    db = getattr(g,"_database",None)
    if db is None:
        db = g._database = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exception):
    db=getattr(g,"_database",None)
    if db is not None: db.close()


# ---------------- INIT DB ----------------
def init_db():
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    c = db.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS admins(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    password TEXT)""")

    # ✅ UPDATED STRUCTURE
    c.execute("""CREATE TABLE IF NOT EXISTS students(
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
    paid INTEGER DEFAULT 0)""")

    c.execute("""CREATE TABLE IF NOT EXISTS payments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt TEXT,
    student_id INTEGER,
    total_amount INTEGER,
    date TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS expenses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    amount INTEGER,
    category TEXT,
    date TEXT)""")

    if not c.execute("SELECT * FROM admins").fetchone():
        c.execute("INSERT INTO admins VALUES(NULL,?,?)",
        ("admin",generate_password_hash("admin123"))),
        

    db.commit()
    db.close()

init_db()


# ---------------- RECEIPT ----------------
def next_receipt():
    db=get_db()
    r=db.execute("SELECT MAX(id) FROM payments").fetchone()[0]
    r = 1 if r is None else r+1
    return f"REC-{str(r).zfill(5)}"


# ---------------- LOGIN ----------------
@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        db=get_db()
        user=db.execute("SELECT * FROM admins WHERE username=?",
        (request.form["username"],)).fetchone()

        if user and check_password_hash(user["password"],request.form["password"]):
            session["user"]=request.form["username"]
            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session: return redirect("/")

    db=get_db()
    students=db.execute("SELECT * FROM students").fetchall()

    collected=db.execute("SELECT SUM(total_amount) t FROM payments").fetchone()["t"] or 0
    expenses=db.execute("SELECT SUM(amount) t FROM expenses").fetchone()["t"] or 0

    pending=sum(safe_int(s["total_fee"])-safe_int(s["paid"]) for s in students)
    profit=collected-expenses

    top_pending=db.execute("""
    SELECT *, (total_fee - paid) as due
    FROM students WHERE total_fee > paid
    ORDER BY due DESC LIMIT 3
    """).fetchall()

    top_expenses=db.execute("SELECT * FROM expenses ORDER BY amount DESC LIMIT 3").fetchall()

    return render_template("dashboard.html",
        students=len(students),
        collected=collected,
        expenses=expenses,
        pending=pending,
        profit=profit,
        top_pending=top_pending,
        top_expenses=top_expenses)




# ---------------- STUDENTS ----------------
@app.route("/students",methods=["GET","POST"])
def students():
    if "user" not in session: return redirect("/")

    db=get_db()

    if request.method=="POST":

        name=request.form["name"]
        cls=request.form["class"]

        if db.execute("SELECT * FROM students WHERE name=? AND class=?",(name,cls)).fetchone():
            return "Student already exists"

        admission_fee=safe_int(request.form.get("admission_fee"))
        tuition_fee=safe_int(request.form.get("tuition_fee"))
        bus_fee=safe_int(request.form.get("bus_fee"))
        computer_fee=safe_int(request.form.get("computer_fee"))
        other_fee=safe_int(request.form.get("other_fee"))

        total=admission_fee+tuition_fee+bus_fee+computer_fee+other_fee

        db.execute("""
        INSERT INTO students
        (admission,name,class,parent,phone,
        admission_fee,tuition_fee,bus_fee,computer_fee,other_fee,total_fee)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (request.form["adm"],name,cls,
         request.form["parent"],request.form["phone"],
         admission_fee,tuition_fee,bus_fee,computer_fee,other_fee,total))

        db.commit()

    filter_type=request.args.get("filter")

    if filter_type=="pending":
        data=db.execute("SELECT *, (total_fee - paid) as due FROM students WHERE total_fee > paid ORDER BY due DESC").fetchall()
    elif filter_type=="paid":
        data=db.execute("SELECT * FROM students WHERE total_fee = paid").fetchall()
    else:
        data=db.execute("SELECT * FROM students ORDER BY id DESC").fetchall()

    return render_template("students.html",students=data,filter_type=filter_type)

# ---------------- EXPENSES ----------------
@app.route("/expenses",methods=["GET","POST"])
def expenses():

    if "user" not in session:
        return redirect("/")

    db = get_db()

    # ADD EXPENSE
    if request.method == "POST":

        title = request.form["title"]
        amount = safe_int(request.form["amount"])
        category = request.form["category"]
        date = request.form.get("date") or str(datetime.date.today())

        db.execute("""
        INSERT INTO expenses(title,amount,category,date)
        VALUES(?,?,?,?)
        """,(title,amount,category,date))

        db.commit()

    # FETCH DATA
    data = db.execute(
    "SELECT * FROM expenses ORDER BY id DESC"
    ).fetchall()

    total = db.execute(
    "SELECT SUM(amount) t FROM expenses"
    ).fetchone()["t"] or 0

    return render_template("expenses.html",expenses=data,total=total)
# ---------------- EDIT ----------------
@app.route("/edit/<int:id>",methods=["GET","POST"])
def edit(id):
    db=get_db()
    student=db.execute("SELECT * FROM students WHERE id=?",(id,)).fetchone()

    if request.method=="POST":

        admission_fee=safe_int(request.form.get("admission_fee"))
        tuition_fee=safe_int(request.form.get("tuition_fee"))
        bus_fee=safe_int(request.form.get("bus_fee"))
        computer_fee=safe_int(request.form.get("computer_fee"))
        other_fee=safe_int(request.form.get("other_fee"))

        total=admission_fee+tuition_fee+bus_fee+computer_fee+other_fee

        db.execute("""UPDATE students SET
        admission=?,name=?,class=?,parent=?,phone=?,
        admission_fee=?,tuition_fee=?,bus_fee=?,computer_fee=?,other_fee=?,total_fee=?
        WHERE id=?""",
        (request.form["adm"],request.form["name"],request.form["class"],
         request.form["parent"],request.form["phone"],
         admission_fee,tuition_fee,bus_fee,computer_fee,other_fee,total,id))

        db.commit()
        return redirect("/students")

    return render_template("edit_student.html",student=student)

    
# ---------------- DELETE STUDENT ----------------
@app.route("/delete/<int:id>")
def delete_student(id):

    if "user" not in session:
        return redirect("/")

    db = get_db()

    db.execute("DELETE FROM payments WHERE student_id=?", (id,))
    db.execute("DELETE FROM students WHERE id=?", (id,))

    db.commit()

    flash("Student Deleted Successfully!")

    return redirect("/students")
# ---------------- PAYMENT ----------------
@app.route("/pay/<int:id>",methods=["GET","POST"])
def pay(id):
    db=get_db()
    student=db.execute("SELECT * FROM students WHERE id=?",(id,)).fetchone()

    if request.method=="POST":
        amount=safe_int(request.form.get("amount"))
        if amount<=0: return "Invalid amount"

        receipt=next_receipt()
        date=request.form.get("date") or str(datetime.date.today())

        db.execute("INSERT INTO payments(receipt,student_id,total_amount,date) VALUES(?,?,?,?)",
        (receipt,id,amount,date))

        db.execute("UPDATE students SET paid = paid + ? WHERE id=?",(amount,id))
        db.commit()

        return redirect("/receipt/"+receipt)

    balance=safe_int(student["total_fee"])-safe_int(student["paid"])
    return render_template("payment.html",student=student,balance=balance)


# ---------------- RECEIPT ----------------
@app.route("/receipt/<rid>")
def receipt(rid):
    db=get_db()
    p=db.execute("SELECT * FROM payments WHERE receipt=?",(rid,)).fetchone()
    s=db.execute("SELECT * FROM students WHERE id=?",(p["student_id"],)).fetchone()

    balance=safe_int(s["total_fee"])-safe_int(s["paid"])

    return render_template("receipt.html",p=p,s=s,balance=balance)


# ---------------- HISTORY ----------------
@app.route("/history/<int:id>")
def history(id):
    db=get_db()
    student=db.execute("SELECT * FROM students WHERE id=?",(id,)).fetchone()
    payments=db.execute("SELECT * FROM payments WHERE student_id=? ORDER BY id DESC",(id,)).fetchall()

    return render_template("history.html",student=student,payments=payments)

# ---------------- EXPORT TRANSACTIONS EXCEL ----------------
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
if __name__=="__main__":
    app.run(debug=False)
