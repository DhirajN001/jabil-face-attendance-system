from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

@app.route("/")
def login():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/employee")
def employee():
    return render_template("employee.html")

@app.route("/save_employee", methods=["POST"])
def save_employee():

    emp_id = request.form["emp_id"]
    name = request.form["name"]
    department = request.form["department"]
    mobile = request.form["mobile"]

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO employees(emp_id,name,department,mobile) VALUES(?,?,?,?)",
        (emp_id, name, department, mobile)
    )

    conn.commit()
    conn.close()

    return redirect("/employees")

@app.route("/employees")
def employees():

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees")
    data = cursor.fetchall()

    conn.close()

    return render_template("employees.html", employees=data)

if __name__ == "__main__":
    app.run(debug=True)