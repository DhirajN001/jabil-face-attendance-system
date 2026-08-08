import cv2
from deepface import DeepFace
import sqlite3
from datetime import datetime
import os

camera = cv2.VideoCapture(0)

while True:

    ret, frame = camera.read()

    cv2.imshow("Face Attendance", frame)

    cv2.imwrite("captured.jpg", frame)

    for file in os.listdir("faces"):

        emp_id = file.replace(".jpg", "")

        result = DeepFace.verify(
            img1_path="captured.jpg",
            img2_path=f"faces/{file}",
            detector_backend="opencv",
            enforce_detection=False
        )

        if result["verified"]:

            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()

            now = datetime.now()

            date = now.strftime("%Y-%m-%d")
            time = now.strftime("%H:%M:%S")

            cursor.execute(
                """
                INSERT INTO attendance (emp_id, date, time, status)
                VALUES (?, ?, ?, ?)
                """,
                (emp_id, date, time, "Present")
            )

            conn.commit()
            conn.close()

            print(f"{emp_id} Attendance Marked ✅")

            camera.release()
            cv2.destroyAllWindows()
            exit()

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()