import cv2
import os

emp_id = input("Enter Employee ID: ")

folder = "faces"
os.makedirs(folder, exist_ok=True)

cap = cv2.VideoCapture(0)

count = 0

while True:

    ret, frame = cap.read()

    cv2.imshow("Capture Face", frame)

    key = cv2.waitKey(1)

    if key == ord("c"):
        filename = f"{folder}/{emp_id}.jpg"
        cv2.imwrite(filename, frame)
        print("Face Saved")
        break

    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()