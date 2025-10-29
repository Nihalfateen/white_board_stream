from mcap.reader import make_reader
import json
import time
import cv2
import numpy as np
import math

file = input("Enter name of MCAP file: ")

if ".mcap" in file:
    mcap_file = f"./replays/{file}"
else:
    mcap_file = f"./replays/{file}.mcap"

class ReplayTool:
    def __init__(self, speed):
        self.play_speed = speed

        self.event_history = []

        self.width = 800
        self.height = 600
        self.sidebar_width = 150
        self.canvas = np.ones((self.height, self.width, 3), dtype=np.uint8) * 255
        self.canvas[:, : self.sidebar_width] = 200
        cv2.imshow("Replay Tool", self.canvas)
        
    def apply_event(self, event):
            tool = event["tool"]
            if tool == "undo":
                for i in range(len(self.event_history) - 1, -1, -1):
                    e = self.event_history[i]
                    if e.get("user_id") == event["user_id"] and e.get("tool") != "undo":
                        self.event_history.pop(i)
                        break
                # Redraw canvas after undo
                self.canvas[:, self.sidebar_width:] = 255
                for e in self.event_history:
                    if e["tool"] != "undo":
                        self.apply_event(e)
                return            
            thickness = event["thickness"]
            color = tuple(event.get("color", (0, 0, 255)))
            points = event.get("points", [])

            if not points:
                return
            if tool in ["line", "freehand"]:
                for i in range(1, len(points)):
                    cv2.line(self.canvas, points[i-1], points[i], color, thickness)
                    cv2.imshow("Replay Tool", self.canvas)
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:  # ESC
                        break
            elif tool == "circle" and len(points) >= 2:
                radius = int(math.hypot(points[0][0] - points[1][0] , points[0][1] - points[1][1]))
                cv2.circle(self.canvas, (points[0]),radius, color, thickness)
            elif tool == "rectangle" and len(points) >= 2:
                cv2.rectangle(self.canvas, points[0], points[1], color, thickness)
            elif tool == "flood fill":
                cv2.floodFill(self.canvas, None, points[0], color)
            self.canvas[:, : self.sidebar_width] = 200

    def run(self):
        cv2.namedWindow("Replay Tool")
        cv2.setWindowProperty("Replay Tool", cv2.WND_PROP_TOPMOST, 1)
        cv2.imshow("Replay Tool", self.canvas)
        cv2.waitKey(1)
        try:
            with open(mcap_file,"rb") as f:
                reader = make_reader(f)
                previous_ts = None
                for schema, channel, message in reader.iter_messages():
                    event = json.loads(message.data.decode("utf-8"))
                    current_ts = message.log_time
                    if previous_ts is None:
                        previous_ts = current_ts
                    dt = (current_ts - previous_ts) /1e9
                    start = time.time()
                    while time.time() - start < dt / self.play_speed:
                        cv2.waitKey(1)
                    previous_ts = current_ts
                    self.apply_event(event)
                    if event["tool"] != "undo":
                        self.event_history.append(event)
                    cv2.imshow("Replay Tool", self.canvas)
                    key = cv2.waitKey(1)  # wait 1 ms for a key event (also allows the window to refresh)
                    if key == 27:  # ESC key to exit
                        break
            print("Finished replay!")
            while True:
                key = cv2.waitKey(1) & 0xFF
                if key == 27:  # ESC
                    break
        except FileNotFoundError:
            print(f"Error: File '{mcap_file}' not found.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
                   
        cv2.destroyAllWindows()
        

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='set playback speed')
    parser.add_argument('--speed', type=int, required=False, help='set playback speed', default=1)
    args = parser.parse_args()
    tool = ReplayTool(speed = args.speed)
    tool.run()


