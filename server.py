import asyncio
import websockets
import json
import random
import time
import math

# Configuration
PORT = 8765
host = "localhost"
TICK_RATE = 60  # Server updates 60 times per second
ARTIFICIAL_LATENCY = 0.2  # 200ms one-way latency
MAP_WIDTH = 800
MAP_HEIGHT = 600
PLAYER_SPEED = 300  # Pixels per second
PLAYER_SIZE = 20    # Radius
COIN_SIZE = 10
COIN_SPAWN_RATE = 3.0 # Seconds

# Game State
class GameServer:
    def __init__(self):
        self.clients = {}  # {websocket: player_id}
        self.players = {}  # {player_id: {x, y, color, score, inputs}}
        self.coins = []    # [{id, x, y}]
        self.coin_counter = 0
        self.last_coin_spawn = time.time()
        self.running = False
        self.start_time = time.time()
        self.next_player_id = 1

    def spawn_coin(self):
        coin = {
            "id": self.coin_counter,
            "x": random.randint(COIN_SIZE, MAP_WIDTH - COIN_SIZE),
            "y": random.randint(COIN_SIZE, MAP_HEIGHT - COIN_SIZE)
        }
        self.coins.append(coin)
        self.coin_counter += 1

    def check_collisions(self, player_id):
        p = self.players[player_id]
        
        # Wall collisions
        p['x'] = max(PLAYER_SIZE, min(MAP_WIDTH - PLAYER_SIZE, p['x']))
        p['y'] = max(PLAYER_SIZE, min(MAP_HEIGHT - PLAYER_SIZE, p['y']))

        # Coin collisions
        remaining_coins = []
        for coin in self.coins:
            dx = p['x'] - coin['x']
            dy = p['y'] - coin['y']
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance < (PLAYER_SIZE + COIN_SIZE):
                # Collected
                p['score'] += 1
                print(f"Player {player_id} collected coin {coin['id']}. Score: {p['score']}")
            else:
                remaining_coins.append(coin)
        
        self.coins = remaining_coins

    def update(self, dt):
        if len(self.players) < 2:
            return  # Lobby mode

        # Spawn coins
        now = time.time()
        if now - self.last_coin_spawn > COIN_SPAWN_RATE:
            self.spawn_coin()
            self.last_coin_spawn = now

        # Process movement based on inputs stored in player state
        for pid, p in self.players.items():
            move_dir = p.get('input', None)
            if move_dir:
                if move_dir == 'UP': p['y'] -= PLAYER_SPEED * dt
                elif move_dir == 'DOWN': p['y'] += PLAYER_SPEED * dt
                elif move_dir == 'LEFT': p['x'] -= PLAYER_SPEED * dt
                elif move_dir == 'RIGHT': p['x'] += PLAYER_SPEED * dt
            
            self.check_collisions(pid)

    async def broadcast_state(self):
        if not self.clients:
            return

        state = {
            "t": time.time(), # Server timestamp for interpolation
            "players": self.players,
            "coins": self.coins,
            "status": "PLAYING" if len(self.players) >= 2 else "WAITING_FOR_PLAYERS"
        }
        serialized = json.dumps(state)

        # Network Simulation: Outbound Latency
        # We spawn a task to send this specific snapshot after a delay
        asyncio.create_task(self.delayed_broadcast(serialized))

    async def delayed_broadcast(self, message):
        await asyncio.sleep(ARTIFICIAL_LATENCY)
        # Send to all connected clients
        if self.clients:
            await asyncio.gather(
                *[ws.send(message) for ws in self.clients], 
                return_exceptions=True
            )

    async def handle_client_message(self, websocket, message):
        # Network Simulation: Inbound Latency
        # We wait 200ms before processing the input to simulate lag arriving at server
        await asyncio.sleep(ARTIFICIAL_LATENCY)

        try:
            data = json.loads(message)
            pid = self.clients.get(websocket)
            
            if not pid: return

            if data['type'] == 'input':
                # Authoritative: We just store the intent. 
                # The update loop applies physics.
                self.players[pid]['input'] = data['direction']
                
        except Exception as e:
            print(f"Error handling message: {e}")

    async def register(self, websocket):
        pid = self.next_player_id
        self.next_player_id += 1
        self.clients[websocket] = pid
        
        # Assign random color and position
        self.players[pid] = {
            "x": random.randint(100, 700),
            "y": random.randint(100, 500),
            "color": (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255)),
            "score": 0,
            "input": None
        }
        
        print(f"Player {pid} connected.")
        
        # Send initial ID assignment (Critical for client to know who they are)
        # We do not lag this initial handshake for simplicity of connection setup, 
        # but gameplay data is lagged.
        await websocket.send(json.dumps({"type": "init", "id": pid}))

    async def unregister(self, websocket):
        pid = self.clients.pop(websocket, None)
        if pid:
            self.players.pop(pid, None)
            print(f"Player {pid} disconnected.")

game = GameServer()

async def handler(websocket):
    await game.register(websocket)
    try:
        async for message in websocket:
            # Handle incoming messages asynchronously so we don't block the loop
            asyncio.create_task(game.handle_client_message(websocket, message))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await game.unregister(websocket)

async def game_loop():
    last_time = time.time()
    while True:
        current_time = time.time()
        dt = current_time - last_time
        last_time = current_time

        game.update(dt)
        await game.broadcast_state()
        
        # Maintain tick rate
        elapsed = time.time() - current_time
        sleep_time = max(0, (1.0 / TICK_RATE) - elapsed)
        await asyncio.sleep(sleep_time)

async def main():
    print(f"Server starting on ws://{host}:{PORT}")
    print(f"Simulating {ARTIFICIAL_LATENCY*1000}ms latency...")
    
    server = await websockets.serve(handler, host, PORT)
    await asyncio.gather(server.wait_closed(), game_loop())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped.")