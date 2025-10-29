import zenoh
import json
import signal
import sys
import time
from datetime import datetime
from mcap.writer import Writer


class WhiteboardStateService:
    # first function run
    def __init__(self):
        self.event_history = []
        self.active_users = set()

        # Zenoh session
        self.session = zenoh.open(zenoh.Config())

        # Keys
        self.key_events = "whiteboard/events"
        self.key_state = "whiteboard/state"
        self.key_users = "whiteboard/users"
        self.key_notifications = "whiteboard/notifications"

        # Subscribers
        self.session.declare_subscriber(self.key_events, self.on_event)
        self.session.declare_subscriber(self.key_users, self.on_user_event)

        # Queryable: clients ask for current state
        self.session.declare_queryable(self.key_state, self.on_state_request)

        print("State Service running. Ctrl+C to stop.")

    # -------------------------
    # Handle drawing events
    # -------------------------
    def on_event(self, sample):
        try:
            msg = json.loads(sample.payload.to_string())
            event = msg.get("event")
            if event["tool"] == "undo":
                for i in range(len(self.event_history) - 1, -1, -1):
                    e = self.event_history[i]
                    if e.get("user_id") == event["user_id"] and e.get("tool") != "undo":
                        self.event_history.pop(i)
                        break
            else:
                self.event_history.append(event)
            # print(len(self.active_users))
            # print(len(self.event_history))
            # print("Event received:", event)
        except Exception as e:
            print("Failed to handle event:", e)
        try:
            ts = int(time.time() * 1e9)
            self.writer.add_message(
                channel_id=self.channel_id,
                log_time=ts,
                publish_time=ts,
                data=json.dumps(event).encode(),
            )
        except Exception as e:
            print("Failed to save event:", e)

    # -------------------------
    # Handle user join/leave
    # -------------------------
    def on_user_event(self, sample):
      try:
        print("On user Event User received:", sample.payload)
        msg = json.loads(bytes(sample.payload).decode())
        

        action = msg.get("action")
        user_id = msg.get("user_id")

        if action == "join":
            if user_id in self.active_users:
                print(f"User {user_id} is already connected — rejecting.")
                self.session.put(
                    self.key_notifications,
                    json.dumps({
                        "type": "error",
                        "user": user_id,
                        "message": "Username already taken"
                    })
                )
                return

            # Add new user
            self.active_users.add(user_id)
            print(f"{user_id} joined")

            # Notify others
            self.session.put(
                self.key_notifications,
                json.dumps({
                    "type": "join",
                    "user": user_id
                })
            )

        elif action == "leave":
            self.active_users.discard(user_id)
            print(f"{user_id} left")

            self.session.put(
                self.key_notifications,
                json.dumps({
                    "type": "leave",
                    "user": user_id
                })
            )

      except Exception as e:
             print("Failed to handle user event:", e)
    # -------------------------
    # Reply to state requests
    # -------------------------
    def on_state_request(self, query):
        try:
            print(query)
            state = {
                "events": self.event_history,
                "active_users": list(self.active_users),
            }
            query.reply(query.selector.key_expr, json.dumps(state))
            print(f"Replied to state request from {query.selector.key_expr}")
        except Exception as e:
            print(" Failed to reply to state request:", e)

    # -------------------------
    # Run service
    # -------------------------
    def run(self):
        def signal_handler(sig, frame):
            print(f"Saved to whiteboard_{timestamp}.mcap")
            self.writer.finish()
            print("\nStopping state service...")
            self.session.close()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        print("State Service ready. Waiting for events and queries...")
        while True:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(f"./replays/whiteboard_{timestamp}.mcap", "wb") as f:
                self.writer = Writer(f)
                self.channel_id = self.writer.register_channel(
                    topic="whiteboard/events", message_encoding="json", schema_id=0
                )
                self.writer.start()
                while True:
                    pass


if __name__ == "__main__":
    service = WhiteboardStateService()
    service.run()
