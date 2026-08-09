
from flask import Flask, render_template, request, redirect, jsonify, session
import base64
import sqlite3
from datetime import datetime
import os
import ast
import pandas as pd
from flask import send_file



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

@app.route("/face_descriptors")
def face_descriptors():
    """Return registered face descriptors for browser-side face-api.js matching."""
    try:
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT emp_id, face_descriptor
            FROM employees
            WHERE face_descriptor IS NOT NULL
              AND face_descriptor != ''
        """)

        rows = cursor.fetchall()
        conn.close()

        result = []

        for emp_id, descriptor_text in rows:
            try:
                descriptor = ast.literal_eval(descriptor_text)

                if isinstance(descriptor, (list, tuple)) and len(descriptor) > 0:
                    result.append({
                        "emp_id": emp_id,
                        "descriptor": list(descriptor)
                    })

            except (ValueError, SyntaxError, TypeError) as descriptor_error:
                print(
                    f"Invalid face descriptor for {emp_id}: "
                    f"{descriptor_error}"
                )

        return jsonify(result)

    except Exception as e:
        print("FACE DESCRIPTORS ERROR:", str(e))
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route("/recognize_face", methods=["POST"])
def recognize_face():
    """
    Browser-side face-api.js sends a 128-value face descriptor.
    Server only compares it with descriptors stored in SQLite.
    No DeepFace/TensorFlow processing is used here.
    """
    try:
        data = request.get_json()

        if not data or "descriptor" not in data:
            return jsonify({
                "success": False,
                "message": "Face descriptor not received"
            }), 400

        incoming = data["descriptor"]

        if not isinstance(incoming, list) or len(incoming) == 0:
            return jsonify({
                "success": False,
                "message": "Invalid face descriptor"
            }), 400

        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT emp_id, face_descriptor
            FROM employees
            WHERE face_descriptor IS NOT NULL
              AND face_descriptor != ''
        """)

        rows = cursor.fetchall()

        if not rows:
            conn.close()
            return jsonify({
                "success": False,
                "message": "No registered face descriptors found"
            })

        # Euclidean distance between two face-api.js 128-D descriptors.
        best_emp_id = None
        best_distance = float("inf")

        for emp_id, descriptor_text in rows:
            try:
                stored = ast.literal_eval(descriptor_text)

                if len(stored) != len(incoming):
                    continue

                distance = sum(
                    (float(incoming[i]) - float(stored[i])) ** 2
                    for i in range(len(incoming))
                ) ** 0.5

                if distance < best_distance:
                    best_distance = distance
                    best_emp_id = emp_id

            except (ValueError, SyntaxError, TypeError) as descriptor_error:
                print(
                    f"Invalid descriptor for {emp_id}: "
                    f"{descriptor_error}"
                )

        # Same starting threshold commonly used by face-api.js.
        MATCH_THRESHOLD = 0.60
        
        print("================================")
        print("BEST EMPLOYEE:", best_emp_id)
        print("BEST DISTANCE:", best_distance)
        print("MATCH THRESHOLD:", MATCH_THRESHOLD)
        print("================================")

        if best_emp_id is None or best_distance >= MATCH_THRESHOLD:
            conn.close()

            return jsonify({
                "success": False,
                "message": "Face not recognized",
                "distance": best_distance
                if best_emp_id is not None else None
            })

        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")

        cursor.execute("""
            SELECT name, department
            FROM employees
            WHERE emp_id = ?
        """, (best_emp_id,))

        employee = cursor.fetchone()

        if employee is None:
            conn.close()

            return jsonify({
                "success": False,
                "message": f"Employee {best_emp_id} not found"
            }), 404

        name, department = employee

        cursor.execute("""
            SELECT *
            FROM attendance
            WHERE emp_id = ? AND date = ?
        """, (best_emp_id, date))

        existing = cursor.fetchone()

        if existing:
            conn.close()

            return jsonify({
                "success": True,
                "already": True,
                "emp_id": best_emp_id,
                "name": name,
                "department": department,
                "time": time,
                "distance": best_distance,
                "message": "Attendance already marked"
            })

        cursor.execute("""
            INSERT INTO attendance
            (emp_id, date, time, status)
            VALUES (?, ?, ?, ?)
        """, (best_emp_id, date, time, "Present"))

        conn.commit()
        conn.close()

        print(
            f"Attendance marked successfully: "
            f"{best_emp_id} - {name} "
            f"(distance={best_distance:.4f})"
        )

        return jsonify({
            "success": True,
            "already": False,
            "emp_id": best_emp_id,
            "name": name,
            "department": department,
            "time": time,
            "distance": best_distance,
            "message": "Attendance Marked Successfully"
        })

    except Exception as e:
        print("RECOGNIZE FACE ERROR:", str(e))

        return jsonify({
            "success": False,
            "message": "Recognition failed",
            "error": str(e)
        }), 500


@app.route("/recognize", methods=["POST"])
def recognize():
    """
    Backward-compatible endpoint.
    The new live.html should send a face descriptor to /recognize_face.
    This endpoint no longer runs DeepFace.
    """
    return jsonify({
        "success": False,
        "message": "Use /recognize_face with a face descriptor."
    }), 400


@app.route("/faces/<path:filename>")
def serve_face(filename):
    from flask import send_from_directory
    return send_from_directory("faces", filename)


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

    if username == "admin" and password == "admin123":

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
    try:
        data = request.get_json()

        if not data or "emp_id" not in data:
            return jsonify({
                "success": False,
                "message": "Employee ID not received"
            }), 400

        emp_id = data["emp_id"]

        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")

        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name, department
            FROM employees
            WHERE emp_id = ?
        """, (emp_id,))

        employee = cursor.fetchone()

        if employee is None:
            conn.close()
            return jsonify({
                "success": False,
                "message": f"Employee {emp_id} not found"
            }), 404

        name, department = employee

        cursor.execute("""
            SELECT *
            FROM attendance
            WHERE emp_id = ? AND date = ?
        """, (emp_id, current_date))

        existing = cursor.fetchone()

        if existing:
            conn.close()

            return jsonify({
                "success": True,
                "already": True,
                "emp_id": emp_id,
                "name": name,
                "department": department,
                "time": current_time,
                "message": "Attendance already marked"
            })

        cursor.execute("""
            INSERT INTO attendance
            (emp_id, date, time, status)
            VALUES (?, ?, ?, ?)
        """, (emp_id, current_date, current_time, "Present"))

        conn.commit()
        conn.close()

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
            "time": current_time,
            "message": "Attendance Marked Successfully"
        })

    except Exception as e:
        print("MARK ATTENDANCE ERROR:", str(e))

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


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