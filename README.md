# PSR - Practical Assigment 1
Collaborative Whiteboard

# Members
- 113977: Rodrigo Bio
- 129359: Nihal Fateen

# Project Description
This project is a real-time collaborative whiteboard application built in Python, enabling multiple users to interact on a shared canvas simultaneously. Users can draw with various tools, select colors, undo actions, save Images and save the session. All drawing events are synchronized across clients in real time using Zenoh, and persistently logged using MCAP, allowing sessions to be replayed or analyzed. The application is designed for robust, cross-platform use, providing a seamless collaborative experience for education, brainstorming, and creative teamwork.

# Features:
- Real-time drawing: Lines drawn on one client appear instantly on all connected clients.
- Undo: Undo the most recent drawing action made by the user.
- Color selection: Choose different pen colors for drawing.
- Save drawings: Capture the current whiteboard view as an image file.
- Cross-platform: Runs on Windows, macOS, and Linux with Python 3.
- Event logging with MCAP: All events (drawing, undo, join/leave) are saved for replay and analysis.
  
# Technologies:

- Python 3.10+
- Zenoh – For real-time publish/subscribe communication (pip install zenoh)
- MCAP – For logging and replaying whiteboard events (pip install mcap)
- OpenCV (cv2) – For canvas rendering and GUI interaction (pip install opencv-python)
- NumPy – For handling canvas arrays (pip install numpy)
- Tkinter – For color selection GUI (standard with Python)
- Datetime – For timestamping events (standard Python library)
- Math – For geometric calculations (standard Python library)
- Signal & sys – For clean shutdown handling (standard Python libraries)
- JSON – For serializing/deserializing events (standard Python library)
- Time – For timestamps and delays (standard Python library)

# Project Structure
```
collaborative_whiteboard_Assignment1/
│
├── state_service.py                 # The main server to handle TCP/Zenoh communication
├── client.py
├── replay_tool.py              
└── README.md
└── requirements.txt                
```
# How it Works:
- Server Setup<br>
  A central Zenoh-based state service listens for incoming client events, maintains the global whiteboard state, and logs all events into MCAP files for later replay.
  
- Client Connection<br>
  When a new client connects, it queries the server for the current state and subscribes to real-time updates from other clients.

- Drawing Data Transmission<br>
  User actions (strokes, colors, positions, tools) are serialized and published via Zenoh. Other clients receive these updates instantly.

- Canvas Rendering<br>
  Each client renders incoming drawing data on their local canvas, keeping all users’ whiteboards synchronized in real-time.

- Event Logging and Replay<br>
  All events are saved in MCAP format with timestamps. Sessions can later be replayed or analyzed using MCAP tools.

# How to make it work:
- Clone the REPO
- Start the State Service<br>
- Run client.py

# Notes
- Each username must be unique, duplicate usernames are not allowed.
- Canvas changes are propagated instantly to all connected clients.
- All events are recorded in MCAP, enabling session replay or auditing.

# License
  This project is open-source and free to use for educational purposes




