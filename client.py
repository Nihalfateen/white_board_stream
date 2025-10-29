import cv2
import numpy as np
import json
import zenoh
from tkinter import colorchooser
import math
import time
import sys
import random


class WhiteboardClient:
    def __init__(
        self,
        username,
        state_server="whiteboard/state",
        events_topic="whiteboard/events",
        users_topic="whiteboard/users",
        notifications_topic="whiteboard/notifications",
    ):
        self.username = username

        self.width = 800
        self.height = 600
        self.sidebar_width = 150
        self.canvas = np.ones((self.height, self.width, 3), dtype=np.uint8) * 255

        # Tools
        self.active_tool = "line"
        self.color = (random.uniform(0,255), random.uniform(0,255), random.uniform(0,255))
        self.prev_x, self.prev_y = None, None

        # Drawing state
        self.drawing = False
        self.redrawing = False
        self.current_points = []

        # Notifications
        self.showing_notification = False
        self.notifications = []
        self.notification_duration = 3.0 
        self.lastShowing = False
        self.lastNumNotif = 0

        # Drawing settings
        self.freehand_min_dist = 15
        self.thickness = 3

        # Zenoh session
        self.session = zenoh.open(zenoh.Config())
        self.state_server = state_server

        self.events_topic = events_topic
        self.users_topic = users_topic
        self.notifications_topic = notifications_topic

        # Subscriptions
        self.sub_events = self.session.declare_subscriber(
            self.events_topic, self.on_remote_event
        )
        self.sub_notifications = self.session.declare_subscriber(
            self.notifications_topic, self.on_notification
        )

        # Wait for username approval
        self.username_accepted = False 
        print("Waiting for username approval from server...", end="", flush=True)
        
        last_sent = 0
        self.request_join = True
        while not self.username_accepted:
            current = int(time.time() * 1000)
            # Request every second
            if current - last_sent >= 1000 and not self.username_accepted:     
                self.send_user_event("join")
                print(".",end="", flush=True)
                last_sent = current
            time.sleep(0.1)
            while not self.request_join:
                time.sleep(0.1)
        print()
            
        # Setup querier (the one that asks)
        self.q = self.session.declare_querier(self.state_server)

        # Publish new events
        self.pub = self.session.declare_publisher(self.events_topic)

    # -------------------------
    # Make a query
    # -------------------------
    def query(self):
        replies = self.q.get()
        return replies

    def request_initial_state(self):
        print("Requesting initial state from state service...")
        try:
            replies = self.query()
            for reply in replies:
                state_json = bytes(reply.ok.payload).decode()
                state = json.loads(state_json)
                self.redrawing = True
                self.canvas[:] = 255
                if state:
                    events = state.get("events", [])
                    users = state.get("active_users", [])

                    print(f"Loaded {len(events)} old events")
                    print(f"Active users: {users}")
                    for event in events:
                        # Avoid applying undo events from history
                        if event["tool"] == "undo": 
                            continue    
                        self.apply_event(event, remote=True)
                else:
                    print("No initial state available")
            self.redrawing = False
            if not self.drawing : 
                self.preview = self.canvas.copy()
        except Exception as e:
            print("Failed to get initial state:", e)

    # -------------------------
    # Send join/leave events
    # -------------------------
    def send_user_event(self, action):
        msg = {"action": action, "user_id": self.username}
        # print(msg)
        self.session.put(self.users_topic, json.dumps(msg).encode())

    # -------------------------
    # Show notifications on canvas
    # -------------------------
    def show_notification(self, text):
        self.notifications.append((text, time.time()))

    def draw_notifications(self):
        current_time = time.time()
        self.notifications = [(txt, ts) for txt, ts in self.notifications if current_time - ts < self.notification_duration]
        y = 30
        self.showing_notification =  bool(self.notifications)
        if self.showing_notification and not self.lastShowing or (len(self.notifications) != self.lastNumNotif): self.preview = self.canvas.copy()
        self.lastNumNotif = len(self.notifications)
        if not self.showing_notification:
            self.lastShowing = False
            return
        self.lastShowing = True
        for txt, _ in self.notifications:
            (text_w, text_h), baseline = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            top_left = (self.sidebar_width + 10, y - text_h - baseline)
            bottom_right = (self.sidebar_width + 10 + text_w, y + baseline)
            cv2.rectangle(self.preview, top_left, bottom_right, (255,255,255), -1)
            cv2.putText(self.preview, txt, (self.sidebar_width + 10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)
            cv2.imshow("Whiteboard", self.preview)
            y += 30

    # -------------------------
    # Handle notifications
    # -------------------------
    def on_notification(self, sample):
      try:
        msg = json.loads(bytes(sample.payload).decode())
        msg_type = msg.get("type")
        user = msg.get("user")

        if msg_type == "error" and user == self.username:
            error_message = msg.get("message")
            print(f"{error_message}")

            self.show_notification(error_message)
            self.request_join = False
            self.username = input("Enter your username: ")
            print("Waiting for username approval from server...",end="",flush=True)
            self.request_join = True

        elif msg_type == "join":
            if user != self.username: 
                self.show_notification(f"{user} joined the session")
                print(f"{user} joined the session")
            else:  
                self.username_accepted = True
                print(f"Username '{self.username}' accepted")

        elif msg_type == "leave":
            if user != self.username:  
                self.show_notification(f"{user} left the session")
                print(f"{user} left the session")

      except Exception as e:
        print("Failed to handle notification:", e)


    # -------------------------
    # Remote drawing events
    # -------------------------
    def on_remote_event(self, sample):
        try:
            msg = json.loads(sample.payload.to_string())
            user_id = msg.get("user_id")
            event = msg.get("event")
            if user_id == self.username:
                return
            print("Message received from user:", user_id)
            print(event)

            def process_event(e):
                if isinstance(e, dict):
                    self.apply_event(e, remote=True)
                elif isinstance(e, list):
                    for sub_e in e:
                        process_event(sub_e)
                else:
                    print("Skipping unsupported type:", type(e), e)

            process_event(event)
            if not self.drawing: 
                self.preview = self.canvas.copy()

        except Exception as e:
            print("Failed to handle remote event:", e)

    # -------------------------
    # Apply drawing events
    # -------------------------
    def publish_event(self, event):
        msg = {"event": event, "user_id": self.username}
        self.pub.put(json.dumps(msg))

    def apply_event(self, event, remote=False):
        tool = event["tool"]
        if event["tool"] == "undo" and remote:
            self.request_initial_state()
            return
        thickness = event["thickness"]
        
        color = tuple(event.get("color", (0, 0, 255)))
        points = event.get("points", [])

        if not points:
            return

        if tool in ["line", "freehand"]:
            for i in range(1, len(points)):
                cv2.line(self.canvas, points[i - 1], points[i], color, thickness)
        elif tool == "circle" and len(points) >= 2:
            radius = int(math.hypot(points[0][0] - points[1][0], points[0][1] - points[1][1]))
            cv2.circle(self.canvas, points[0], radius, color, thickness)
        elif tool == "rectangle" and len(points) >= 2:
            cv2.rectangle(self.canvas, points[0], points[1], color, thickness)
        elif tool == "flood fill":
            cv2.floodFill(self.canvas, None, points[0], color)
        
        if not remote and tool != "undo":
            event["user_id"] = self.username
            self.publish_event(event)

    # ------------------------
    # Draw previews
    # -------------------------
    def draw_free(self, x, y):
        if self.prev_x is None or self.prev_y is None:
            self.prev_x, self.prev_y = x, y
            return

        dx = x - self.prev_x
        dy = y - self.prev_y
        distance = math.hypot(dx, dy)
        if distance < self.freehand_min_dist:
            return

        cv2.line(
            self.preview,
            (int(self.prev_x), int(self.prev_y)),
            (int(x), int(y)),
            self.color,
            self.thickness,
        )
        self.current_points.append((x, y))
        self.prev_x, self.prev_y = x, y
        cv2.imshow("Whiteboard", self.preview)

    def update_preview(self, x, y):
        if self.prev_x is None or self.prev_y is None:
            return

        self.preview = self.canvas.copy()
        start = (int(self.prev_x), int(self.prev_y))
        end = (int(x), int(y))

        if self.active_tool == "line":
            cv2.line(self.preview, start, end, self.color, self.thickness)
        elif self.active_tool == "rectangle":
            cv2.rectangle(self.preview, start, end, self.color, self.thickness)
        elif self.active_tool == "circle":
            radius = int(math.hypot(x - self.prev_x, y - self.prev_y))
            cv2.circle(self.preview, start, radius, self.color, self.thickness)

        cv2.imshow("Whiteboard", self.preview)

    # -------------------------
    # Mouse callback
    # -------------------------
    def mouse_callback(self, event, x, y, flags, param):
        if x < self.sidebar_width and not self.drawing:
            if event == cv2.EVENT_LBUTTONDOWN:
                if 50 < y < 90:
                    self.set_tool("line")
                elif 110 < y < 150:
                    self.set_tool("circle")
                elif 170 < y < 210:
                    self.set_tool("rectangle")
                elif 230 < y < 270:
                    self.set_tool("freehand")
                elif 290 < y < 330:
                    self.set_tool("flood fill")
                elif 350 < y < 390:
                    self.set_tool("undo")
                    self.undo()
                elif 410 < y < 450:
                    self.set_tool("save")
                    self.save()
                elif 470 < y < 510:
                    if 0 < x < 52:
                        self.thickness = 3
                    elif 55 < x < 97:
                        self.thickness = 5
                    else:
                        self.thickness = 7
                elif 540 < y < 580:
                    self.choose_color()
        else:
            if self.active_tool in [
                "line",
                "freehand",
                "rectangle",
                "circle",
                "flood fill",
                "undo",
                "save",
                "color",
            ]:
                if event == cv2.EVENT_LBUTTONDOWN:
                    self.preview = self.canvas.copy()
                    self.drawing = True
                    self.prev_x, self.prev_y = x, y
                    self.current_points = [(x, y)]

                elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
                        if self.active_tool=="freehand":
                           self.draw_free(x, y)
                        else:
                          self.update_preview(x, y)

                elif event == cv2.EVENT_LBUTTONUP and self.drawing:
                    
                    self.drawing = False
                    self.current_points.append((x, y))
                    event_data = {
                        "tool": self.active_tool,
                        "color": self.color,
                        "points": self.current_points,
                        "user_id": self.username,
                        "thickness": self.thickness
                    }
                    self.apply_event(event_data, remote=False)

                    self.prev_x, self.prev_y = None, None

    # -------------------------
    # Sidebar tools
    # -------------------------
    def set_tool(self, tool):
        self.active_tool = tool.lower()
        print("Active tool:", self.active_tool)

    def choose_color(self):
        prev_tool = self.active_tool
        self.set_tool("color")
        _, hex_color = colorchooser.askcolor(title="Choose color")
        if hex_color:
            self.color = tuple(int(hex_color[i : i + 2], 16) for i in (5, 3, 1))
        self.set_tool(prev_tool)

    def undo(self):
        undo_event = {"tool": "undo", "user_id": self.username}
        self.publish_event(undo_event)
        time.sleep(0.1)
        self.request_initial_state()

    def save(self):
        cv2.imwrite("whiteboard.png", self.canvas)
        print("Saved whiteboard as whiteboard.png")

    def draw_sidebar(self):
        self.canvas[:, : self.sidebar_width] = 200
        buttons = [
            ("Line", 50, 90),
            ("Circle", 110, 150),
            ("Rectangle", 170, 210),
            ("Freehand", 230, 270),
            ("Flood Fill", 290, 330),
            ("Undo", 350, 390),
            ("Save", 410, 450),
            
        ]
        for label, y_start, y_end in buttons:
            if self.active_tool and label.lower() in self.active_tool:
                cv2.rectangle(
                    self.canvas,
                    (10, y_start),
                    (self.sidebar_width - 10, y_end),
                    (100, 100, 100),
                    -1,
                )
                text_color = (0, 0, 0)
            else:
                cv2.rectangle(
                    self.canvas,
                    (10, y_start),
                    (self.sidebar_width - 10, y_end),
                    (150, 150, 150),
                    -1,
                )
                text_color = (255, 255, 255)
            cv2.putText(
                self.canvas,
                label,
                (20, y_start + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                text_color,
                2,
            )
        bg_thickness_btn = [(150, 150, 150),(150, 150, 150),(150, 150, 150)]
        bg_thickness_btn[(self.thickness - 3) // 2] = (100, 100, 100)
        cv2.rectangle(self.canvas,(10, 470),(50, 510),bg_thickness_btn[0],-1)
        cv2.circle(self.canvas,(30, 490), 3,(255, 255, 255),-1)
        cv2.rectangle(self.canvas,(55, 470),(95, 510),bg_thickness_btn[1],-1)
        cv2.circle(self.canvas,(75, 490), 5,(255, 255, 255),-1)
        cv2.rectangle(self.canvas,(100, 470),(140, 510),bg_thickness_btn[2],-1)
        cv2.circle(self.canvas,(120, 490), 7,(255, 255, 255),-1)

        cv2.rectangle(
            self.canvas, (30, 540), (self.sidebar_width - 30, 580), self.color, -1
        )
        cv2.rectangle(
            self.canvas, (30, 540), (self.sidebar_width - 30, 580), (100, 100, 100), 2
        )
      

    # -------------------------
    # Keyboard input
    # -------------------------
    def handle_key(self, key):
        if key == 49: self.thickness = 3
        elif key == 50: self.thickness = 5
        elif key == 51: self.thickness = 7
        elif key == ord("l"): self.set_tool("line")
        elif key == ord("c"): self.set_tool("circle")
        elif key == ord("r"): self.set_tool("rectangle")
        elif key == ord("f"): self.set_tool("freehand")
        elif key == ord("b"): self.set_tool("flood fill") 
        elif key == 26: # Ctrl+Z
            self.set_tool("undo")
            self.undo()
        elif key == ord("s"):
            self.set_tool("save")
            self.save()
        elif key == ord("k"):
            self.choose_color()
        elif key == ord("h"):
            self.show_notification("Keyboard shortcuts:")
            self.show_notification(" l - Line tool, c - Circle tool")
            self.show_notification(" r - Rectangle tool, f - Freehand tool")
            self.show_notification(" k - Color picker, 1/2/3 - Thickness")
            self.show_notification(" s - Save whiteboard as PNG, q - Quit application")
            self.show_notification(" Ctrl+Z - Undo")
        elif key == ord("q"):
            self.send_user_event("leave")
            self.session.close()
            cv2.destroyAllWindows()
            sys.exit(0)
        else:    
            print("Unknown key:", key)
    
    # -------------------------
    # Main loop
    # -------------------------
    def run(self):
        cv2.namedWindow("Whiteboard")
        cv2.setMouseCallback("Whiteboard", self.mouse_callback)

        try:
            self.request_initial_state()
            self.draw_sidebar()
            self.preview = self.canvas.copy()
            while True:
                self.draw_sidebar()
                self.draw_notifications()
                if not self.drawing and not self.redrawing and not self.showing_notification:
                    cv2.imshow("Whiteboard", self.canvas)
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                if key != 255:
                    self.handle_key(key)
        except KeyboardInterrupt:
            self.send_user_event("leave")
            self.session.close()
            cv2.destroyAllWindows()
            sys.exit(0)
        finally:
            self.send_user_event("leave")
            self.session.close()
            cv2.destroyAllWindows()
            
def start_client():
    username = input("Enter your username: ")
    client = WhiteboardClient(username=username)
    client.run()

if __name__ == "__main__":
    start_client()
