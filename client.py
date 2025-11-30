import asyncio
import websockets
import json
import pygame
import sys
import time

# Configuration
SERVER_URI = "ws://localhost:8765"
WIDTH, HEIGHT = 800, 600
PLAYER_SIZE = 20
COIN_SIZE = 10
INTERPOLATION_OFFSET = 0.1  # 100ms buffer for smoothness (on top of network lag)

class GameClient:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Coin Collector - Connecting...")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 24)
        
        self.my_id = None
        self.connected = False
        
        self.state_buffer = [] 
        
        self.current_input = None
        self.last_input_sent = None

    def linear_interpolate(self, start, end, alpha):
        return start + (end - start) * alpha

    def get_render_state(self):
        """
        Computes the interpolated state of players based on buffered server snapshots.
        returns: (players_dict, coins_list, status)
        """
        current_server_time = time.time()
        
        render_time = current_server_time - INTERPOLATION_OFFSET
        
        while len(self.state_buffer) > 2 and self.state_buffer[1]['recv_time'] < render_time:
            self.state_buffer.pop(0)

        if len(self.state_buffer) < 2:
            if self.state_buffer:
                return self.state_buffer[-1]['players'], self.state_buffer[-1]['coins'], self.state_buffer[-1]['status']
            return {}, [], "CONNECTING"

        prev_state = self.state_buffer[0]
        next_state = self.state_buffer[1]

        time_diff = next_state['recv_time'] - prev_state['recv_time']
        if time_diff <= 0: alpha = 1.0
        else: alpha = (render_time - prev_state['recv_time']) / time_diff
        
        alpha = max(0.0, min(1.0, alpha))

        interpolated_players = {}
        
        for pid, p_next in next_state['players'].items():
            if pid in prev_state['players']:
                p_prev = prev_state['players'][pid]
                
                # Lerp X and Y
                interp_x = self.linear_interpolate(p_prev['x'], p_next['x'], alpha)
                interp_y = self.linear_interpolate(p_prev['y'], p_next['y'], alpha)
                
                interpolated_players[pid] = {
                    "x": interp_x,
                    "y": interp_y,
                    "color": p_next['color'],
                    "score": p_next['score']
                }
            else:
                # New player just appeared, snap to position
                interpolated_players[pid] = p_next

        return interpolated_players, next_state['coins'], next_state['status']

    def draw(self, players, coins, status):
        self.screen.fill((30, 30, 30))

        if status == "WAITING_FOR_PLAYERS":
            text = self.font.render("Waiting for Player 2...", True, (255, 255, 255))
            self.screen.blit(text, (WIDTH//2 - 100, HEIGHT//2))
        
        # Draw Coins
        for coin in coins:
            pygame.draw.circle(self.screen, (255, 215, 0), (int(coin['x']), int(coin['y'])), COIN_SIZE)

        # Draw Players
        for pid, p in players.items():
            color = p['color']
            # Highlight self
            if int(pid) == self.my_id:
                pygame.draw.circle(self.screen, (255, 255, 255), (int(p['x']), int(p['y'])), PLAYER_SIZE + 2, 2)
            
            pygame.draw.circle(self.screen, color, (int(p['x']), int(p['y'])), PLAYER_SIZE)
            
            # Draw Score above player
            score_text = self.font.render(str(p['score']), True, (255, 255, 255))
            self.screen.blit(score_text, (int(p['x']) - 5, int(p['y']) - 40))

        # UI
        latency_text = self.font.render(f"Simulated Latency: ~200ms", True, (100, 100, 100))
        self.screen.blit(latency_text, (10, HEIGHT - 30))
        
        pygame.display.flip()

    async def network_loop(self):
        async with websockets.connect(SERVER_URI) as websocket:
            self.connected = True
            
            receive_task = asyncio.create_task(self.receive_handler(websocket))
            
            try:
                while True:
                    # Input Handling
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            return

                    keys = pygame.key.get_pressed()
                    direction = None
                    if keys[pygame.K_w] or keys[pygame.K_UP]: direction = "UP"
                    elif keys[pygame.K_s] or keys[pygame.K_DOWN]: direction = "DOWN"
                    elif keys[pygame.K_a] or keys[pygame.K_LEFT]: direction = "LEFT"
                    elif keys[pygame.K_d] or keys[pygame.K_RIGHT]: direction = "RIGHT"

                    if direction != self.current_input:
                        self.current_input = direction
                        msg = {"type": "input", "direction": direction}
                        await websocket.send(json.dumps(msg))

                    # Game Loop Tick
                    players, coins, status = self.get_render_state()
                    self.draw(players, coins, status)
                    
                    if self.my_id:
                        pygame.display.set_caption(f"Coin Collector - Player {self.my_id}")

                    await asyncio.sleep(1/60) # 60 FPS Client
            
            finally:
                receive_task.cancel()

    async def receive_handler(self, websocket):
        try:
            async for message in websocket:
                data = json.loads(message)
                
                # Handshake
                if "type" in data and data["type"] == "init":
                    self.my_id = data["id"]
                    print(f"Assigned ID: {self.my_id}")
                    continue

                # Game State Update
                if "players" in data:
                    # We attach a local receive timestamp for interpolation logic
                    data['recv_time'] = time.time()
                    self.state_buffer.append(data)
                    
        except Exception as e:
            print(f"Connection error: {e}")

if __name__ == "__main__":
    client = GameClient()
    try:
        asyncio.run(client.network_loop())
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()