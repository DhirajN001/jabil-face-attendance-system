import cv2

camera = cv2.VideoCapture(0)

while True:

    success, frame = camera.read()

    cv2.imshow("Jabil Face Attendance", frame)

    key = cv2.waitKey(1)

    if key == 27:
        break

camera.release()
cv2.destroyAllWindows()