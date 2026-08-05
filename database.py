import sqlite3

def create_database():
    conn = sqlite3.connect("attendance.db")

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_id TEXT UNIQUE,
        name TEXT,
        department TEXT,
        mobile TEXT
    )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_database()
    print("Database Created Successfully")