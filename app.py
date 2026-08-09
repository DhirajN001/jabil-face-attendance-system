
from flask import Flask, render_template, request, redirect, jsonify, session
from deepface import DeepFace
import base64
import sqlite3
from datetime import datetime
import os
import pandas as pd
from flask import send_file
import pyttsx3

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import tensorflow as tf

tf.config.set_visible_devices([], "GPU")

app = Flask(__name__)
app.secret_key = "jabil_face_attendance_2026"

def init_database():

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    # Employees table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT,
            mobile TEXT
            face_descriptor TEXT
        )
    """)

    # Attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    try:
        cursor.execute(
        "ALTER TABLE employees ADD COLUMN face_descriptor TEXT"
    )
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
init_database()

@app.route("/recognize_face", methods=["POST"])
def recognize_face():

    try:

        data = request.json

        descriptor = data["descriptor"]

        # Existing employee face files
        for file_name in os.listdir("faces"):

            if not file_name.lower().endswith(".jpg"):
                continue

            emp_id = file_name.rsplit(".", 1)[0]

            # Temporary response for testing
            # Actual descriptor comparison will be added next

            return jsonify({
                "success": False,
                "message": "Face recognition setup is ready"
            })

        return jsonify({
            "success": False,
            "message": "No employee face found"
        })

    except Exception as e:

        print("Face recognition error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        })


@app.route("/recognize", methods=["POST"])
def recognize():

    try:

        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({
                "success": False,
                "message": "Image not received"
            }), 400

        image = data["image"]

        # Remove base64 header
        if "," in image:
            image = image.split(",", 1)[1]

        image_bytes = base64.b64decode(image)

        # Save captured image
        captured_path = "captured.jpg"

        with open(captured_path, "wb") as file:
            file.write(image_bytes)

        # Make sure faces directory exists
        os.makedirs("faces", exist_ok=True)

        face_files = os.listdir("faces")

        if not face_files:
            return jsonify({
                "success": False,
                "message": "No registered faces found"
            })

        # Check every registered face
        for file_name in face_files:

            if not file_name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            emp_id = os.path.splitext(file_name)[0]

            face_path = os.path.join("faces", file_name)

            print("Checking face:", emp_id)

            result = DeepFace.verify(
                img1_path=captured_path,
                img2_path=face_path,
                detector_backend="opencv",
                enforce_detection=False
            )

            print("Verification result:", result["verified"])

            if result["verified"]:

                conn = sqlite3.connect("attendance.db")
                cursor = conn.cursor()

                now = datetime.now()

                date = now.strftime("%Y-%m-%d")
                time = now.strftime("%H:%M:%S")

                # Check today's attendance
                cursor.execute(
                    """
                    SELECT *
                    FROM attendance
                    WHERE emp_id = ? AND date = ?
                    """,
                    (emp_id, date)
                )

                existing = cursor.fetchone()

                # Get employee information
                cursor.execute(
                    """
                    SELECT name, department
                    FROM employees
                    WHERE emp_id = ?
                    """,
                    (emp_id,)
                )

                employee = cursor.fetchone()

                if employee is None:

                    conn.close()

                    return jsonify({
                        "success": False,
                        "message": f"Employee {emp_id} not found"
                    }), 404

                name = employee[0]
                department = employee[1]

                # Already marked
                if existing:

                    conn.close()

                    return jsonify({
                        "success": True,
                        "already": True,
                        "emp_id": emp_id,
                        "name": name,
                        "department": department,
                        "time": time,
                        "message": "Attendance already marked"
                    })

                # Mark attendance
                cursor.execute(
                    """
                    INSERT INTO attendance
                    (emp_id, date, time, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (emp_id, date, time, "Present")
                )

                conn.commit()
                conn.close()

                # DO NOT USE pyttsx3 on Render
                print(
                    f"Attendance marked successfully: "
                    f"{emp_id} - {name}"
                )

                return jsonify({
                    "success": True,
                    "already": False,
                    "emp_id": emp_id,
                    "name": name,
                    "department": department,
                    "time": time,
                    "message": "Attendance Marked Successfully"
                })

        # No face matched
        return jsonify({
            "success": False,
            "message": "Face not recognized"
        })

    except Exception as e:

        print("RECOGNIZE ERROR:", str(e))

        return jsonify({
            "success": False,
            "message": "Recognition failed",
            "error": str(e)
        }), 500

@app.route("/camera")
def camera():
    return render_template("camera.html")


@app.route("/")
def login():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def do_login():

    username = request.form["username"]
    password = request.form["password"]

    if username == "admin" and password == "Dhiraj123":

        session["user"] = username

        return redirect("/dashboard")

    return "Invalid Username or Password"

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    # Total employees

    cursor.execute("SELECT COUNT(*) FROM employees")
    total_employees = cursor.fetchone()[0]

    # Present employees

    cursor.execute(
        """
        SELECT COUNT(DISTINCT emp_id)
        FROM attendance
        WHERE date = ?
        """,
        (today,)
    )

    present_employees = cursor.fetchone()[0]

    # Absent employees

    absent_employees = total_employees - present_employees

    conn.close()

    return render_template(
        "dashboard.html",
        total_employees=total_employees,
        present_employees=present_employees,
        absent_employees=absent_employees,
        today=today
    )
 
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")
    
@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():

    from datetime import datetime

    data = request.get_json()

    emp_id = data["emp_id"]

    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO attendance (emp_id, date, time, status)
        VALUES (?, ?, ?, ?)
        """,
        (emp_id, current_date, current_time, "Present")
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Attendance marked successfully!"
    })
@app.route("/attendance")
def attendance():

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
    attendance.id,
    attendance.emp_id,
    employees.name,
    attendance.date,
    attendance.time,
    attendance.status
    FROM attendance
    INNER JOIN employees
    ON attendance.emp_id = employees.emp_id
    ORDER BY attendance.id DESC
    """)

    data = cursor.fetchall()

    conn.close()

    return render_template("attendance.html", attendance=data)

@app.route("/test")
def test():

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO attendance (emp_id, date, time, status)
        VALUES (?, ?, ?, ?)
        """,
        ("VD10000618", "2026-08-05", "19:30:00", "Present")
    )

    conn.commit()
    conn.close()

    return "Attendance Added Successfully"


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

@app.route("/save_photo", methods=["POST"])
def save_photo():

    try:

        data = request.get_json()

        emp_id = data["emp_id"]
        image = data["image"]
        descriptor = data["descriptor"]


        # Remove base64 header
        image = image.split(",")[1]

        image_bytes = base64.b64decode(image)


        # Create faces folder
        os.makedirs("faces", exist_ok=True)


        # Save employee face image
        with open(f"faces/{emp_id}.jpg", "wb") as file:

            file.write(image_bytes)


        # Save face descriptor in database
        conn = sqlite3.connect("attendance.db")

        cursor = conn.cursor()


        cursor.execute(
            """
            UPDATE employees
            SET face_descriptor = ?
            WHERE emp_id = ?
            """,
            (
                str(descriptor),
                emp_id
            )
        )


        conn.commit()

        conn.close()


        return jsonify({

            "success": True,

            "emp_id": emp_id,

            "message": "Face registered successfully"

        })


    except Exception as e:

        print("Save face error:", e)

        return jsonify({

            "success": False,

            "message": str(e)

        })

@app.route("/employees")
def employees():

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees")
    data = cursor.fetchall()

    conn.close()

    return render_template("employees.html", employees=data)

@app.route("/delete_employee/<int:id>")
def delete_employee(id):

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM employees WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/employees")

@app.route("/edit_employee/<int:id>")
def edit_employee(id):

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM employees WHERE id=?",
        (id,)
    )

    employee = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_employee.html",
        employee=employee
    )

@app.route("/update_employee", methods=["POST"])
def update_employee():

    id = request.form["id"]
    name = request.form["name"]
    department = request.form["department"]
    mobile = request.form["mobile"]

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE employees
        SET name=?, department=?, mobile=?
        WHERE id=?
        """,
        (name, department, mobile, id)
    )

    conn.commit()
    conn.close()

    return redirect("/employees")

@app.route("/live")
def live():
    return render_template("live.html")

@app.route("/export")

def export():

    conn = sqlite3.connect("attendance.db")

    query = """
    SELECT
    attendance.emp_id,
    employees.name,
    attendance.date,
    attendance.time,
    attendance.status
    FROM attendance
    INNER JOIN employees
    ON attendance.emp_id = employees.emp_id
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    file_name = "attendance.xlsx"

    df.to_excel(file_name, index=False)

    return send_file(
        file_name,
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(debug=True)