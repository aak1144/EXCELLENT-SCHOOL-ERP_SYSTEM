from flask import Flask, render_template, request, redirect, session, flash, send_file
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import pandas as pd
import datetime
import os

app = Flask(__name__)
app.secret_key = "school_erp_secret"

# ---------------- MONGODB ----------------

client = MongoClient(os.environ.get("MONGO_URI"))

db = client["school_erp"]

students_collection = db["students"]
payments_collection = db["payments"]
expenses_collection = db["expenses"]
admins_collection = db["admins"]

# ---------------- DEFAULT ADMIN ----------------

if admins_collection.count_documents({}) == 0:

    admins_collection.insert_one({
        "username": "admin",
        "password": generate_password_hash("admin123")
    })

# ---------------- LOGIN ----------------

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = admins_collection.find_one({
            "username": username
        })

        if user and check_password_hash(user["password"], password):

            session["user"] = username

            return redirect("/dashboard")

        flash("Invalid Login")

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

    students = list(students_collection.find())

    collected = 0
    pending = 0
    expenses = 0

    for p in payments_collection.find():
        collected += int(p.get("amount", 0))

    for e in expenses_collection.find():
        expenses += int(e.get("amount", 0))

    for s in students:
        pending += (
            int(s.get("total_fee", 0))
            - int(s.get("paid", 0))
        )

    return render_template(
        "dashboard.html",
        students=len(students),
        collected=collected,
        pending=pending,
        expenses=expenses
    )

# ---------------- STUDENTS ----------------

@app.route("/students", methods=["GET", "POST"])
def students():

    if "user" not in session:
        return redirect("/")

    if request.method == "POST":

        admission_fee = int(request.form.get("admission_fee") or 0)
        tuition_fee = int(request.form.get("tuition_fee") or 0)
        bus_fee = int(request.form.get("bus_fee") or 0)
        computer_fee = int(request.form.get("computer_fee") or 0)
        other_fee = int(request.form.get("other_fee") or 0)

        total = (
            admission_fee +
            tuition_fee +
            bus_fee +
            computer_fee +
            other_fee
        )

        students_collection.insert_one({

            "admission": request.form["adm"],
            "name": request.form["name"],
            "class": request.form["class"],
            "parent": request.form["parent"],
            "phone": request.form["phone"],

            "admission_fee": admission_fee,
            "tuition_fee": tuition_fee,
            "bus_fee": bus_fee,
            "computer_fee": computer_fee,
            "other_fee": other_fee,

            "total_fee": total,
            "paid": 0
        })

        flash("Student Added Successfully!")

        return redirect("/students")

    students = list(
        students_collection.find().sort("_id", -1)
    )

    return render_template(
        "students.html",
        students=students
    )

# ---------------- DELETE STUDENT ----------------

@app.route("/delete/<id>")
def delete_student(id):

    students_collection.delete_one({
        "_id": ObjectId(id)
    })

    payments_collection.delete_many({
        "student_id": id
    })

    flash("Student Deleted Successfully!")

    return redirect("/students")

# ---------------- PAYMENT ----------------

@app.route("/pay/<id>", methods=["GET", "POST"])
def pay(id):

    student = students_collection.find_one({
        "_id": ObjectId(id)
    })

    if request.method == "POST":

        amount = int(request.form["amount"])

        receipt = "REC-" + str(
            payments_collection.count_documents({}) + 1
        ).zfill(5)

        payments_collection.insert_one({

            "receipt": receipt,
            "student_id": id,
            "amount": amount,
            "date": str(datetime.date.today())
        })

        students_collection.update_one(
            {"_id": ObjectId(id)},
            {
                "$inc": {
                    "paid": amount
                }
            }
        )

        return redirect("/receipt/" + receipt)

    balance = (
        int(student["total_fee"])
        - int(student["paid"])
    )

    return render_template(
        "payment.html",
        student=student,
        balance=balance
    )

# ---------------- RECEIPT ----------------

@app.route("/receipt/<receipt>")
def receipt(receipt):

    payment = payments_collection.find_one({
        "receipt": receipt
    })

    student = students_collection.find_one({
        "_id": ObjectId(payment["student_id"])
    })

    balance = (
        int(student["total_fee"])
        - int(student["paid"])
    )

    return render_template(
        "receipt.html",
        p=payment,
        s=student,
        balance=balance
    )

# ---------------- HISTORY ----------------

@app.route("/history/<id>")
def history(id):

    student = students_collection.find_one({
        "_id": ObjectId(id)
    })

    payments = list(
        payments_collection.find({
            "student_id": id
        })
    )

    return render_template(
        "history.html",
        student=student,
        payments=payments
    )
# ---------------- EXPENSES ----------------

@app.route("/expenses", methods=["GET", "POST"])
def expenses():

    if "user" not in session:
        return redirect("/")

    if request.method == "POST":

        expenses_collection.insert_one({

            "title": request.form["title"],
            "amount": int(request.form["amount"]),
            "category": request.form["category"],
            "date": str(datetime.date.today())

        })

        flash("Expense Added Successfully!")

        return redirect("/expenses")

    expenses = list(
        expenses_collection.find().sort("_id", -1)
    )

    return render_template(
        "expenses.html",
        expenses=expenses
    )
    # ---------------- EDIT STUDENT ----------------

@app.route("/edit/<id>", methods=["GET", "POST"])
def edit_student(id):

    student = students_collection.find_one({
        "_id": ObjectId(id)
    })

    if request.method == "POST":

        admission_fee = int(request.form.get("admission_fee") or 0)
        tuition_fee = int(request.form.get("tuition_fee") or 0)
        bus_fee = int(request.form.get("bus_fee") or 0)
        computer_fee = int(request.form.get("computer_fee") or 0)
        other_fee = int(request.form.get("other_fee") or 0)

        total = (
            admission_fee +
            tuition_fee +
            bus_fee +
            computer_fee +
            other_fee
        )

        students_collection.update_one(

            {"_id": ObjectId(id)},

            {
                "$set": {

                    "admission": request.form["adm"],
                    "name": request.form["name"],
                    "class": request.form["class"],
                    "parent": request.form["parent"],
                    "phone": request.form["phone"],

                    "admission_fee": admission_fee,
                    "tuition_fee": tuition_fee,
                    "bus_fee": bus_fee,
                    "computer_fee": computer_fee,
                    "other_fee": other_fee,

                    "total_fee": total
                }
            }
        )

        flash("Student Updated Successfully!")

        return redirect("/students")

    return render_template(
        "edit_student.html",
        student=student
    )
# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)