# Multiplayer Coin Collector (Latency Test)

A networked multiplayer game written in Python using asyncio and raw websockets. It demonstrates server-authoritative state synchronization and client-side entity interpolation under simulated high-latency conditions (200ms).

## Architecture

### Server (server.py):

### Authoritative source of truth.

Runs the physics loop (collisions, movement) at 60Hz.

Simulates Latency: Adds a 0.2s (200ms) delay to every input received and every state update broadcasted.

### Client (client.py):

### Sends raw inputs (UP/DOWN/LEFT/RIGHT) to the server.

### Interpolation: Does not draw raw data immediately. Instead, it buffers server snapshots and renders the state slightly in the past (Interpolates between two snapshots). This ensures that despite the 200ms lag and network jitter, movement appears buttery smooth.

## Requirements

Python 3.8+

pygame (Rendering)

websockets (Networking)

## Installation

Create a virtual environment (optional but recommended):

```
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### Install dependencies:

```
pip install -r requirements.txt
```


How to Run

Start the Server:
Open a terminal and run:

```
python server.py
```

You will see a message indicating the server is running on port 8765 with 200ms latency.

Start Player 1:
Open a new terminal and run:

```
python client.py
```

Start Player 2:
Open a third terminal and run:
```
python client.py
```
Controls

Arrow Keys or WASD: Move your circle.

Objective: Collect the Gold Coins to increase your score.

Note: The game only starts spawning coins once two players are connected.

Evaluating Smoothness

Even though the server enforces a strict 200ms delay on inputs (you will feel the input lag, which is intentional behavior for this test), the movement of the other player should appear smooth and not "teleporty." This confirms the Entity Interpolation is working correctly.