from typing import List, Tuple, Dict, Set, Optional, Union, Any, Iterable
from itertools import combinations

import sys
from time import sleep
from random import choice

from PodSixNet.Server import Server
from PodSixNet.Channel import Channel


MAX_ELO_DIFFERENCE = 300
HIGH_ELO_DIFFERENCE = 200
BASE_ELO_POINTS = 100

MAX_DISTANCE = 2

BOARD_WIDTH = 9 # columns
BOARD_HEIGHT = 7 # rows

class ClientChannel(Channel):   
    def __init__(self, *args, **kwargs):
        Channel.__init__(self, *args, **kwargs)
        self.nickname = "anonymous"
        self.status = "waiting" # "waiting" or "playing"
        self.opponent = None # Nickname of the current opponent
        self.game_id = None # Current game ID
        self.elo = 1000 # ELO (score)
        self.pending_invitation = None # If there is an incoming game invitation
    
    def Close(self):
        """"Called when the client disconnects"""
        self._server.DelPlayer(self)
    
    def Network_nickname(self, data: Dict[str, str]) -> None:
        """"To Change player's nickname
        
        Args:
            data: Dictionary containing new nickname under "nickname" key """
            
        self.nickname = data["nickname"]
        self._server.UpdateLobby()
    
    def Network_invite(self, data: Dict[str, str]) -> None:
        """"To check if 2 players can confront"""
        opponent_nick = data["opponent"]
        opponent = self._server.FindPlayer(opponent_nick)
    
        if opponent and opponent.status == "waiting":
            elo_diff = abs(self.elo - opponent.elo)
    
            if elo_diff > MAX_ELO_DIFFERENCE:
                self.Send({
                    "action": "invite_error", 
                    "message": f"ELO difference too large ({elo_diff} > 300)"
                    })
                return
        
            if HIGH_ELO_DIFFERENCE <= elo_diff <= MAX_ELO_DIFFERENCE and self.elo > opponent.elo:
                # Send invitation that can be declined
                opponent.pending_invitation = {
                    "from": self.nickname,
                    "from_elo": self.elo,
                    "elo_diff": elo_diff
                    }
                opponent.Send({
                    "action": "invite_request",
                    "from": self.nickname,
                    "from_elo": self.elo,
                    "elo_diff": elo_diff,
                    "forced": False  # Player can decline
                    })
                return
        
            # If ELO difference < 200 or inviting player has lower ELO, match is forced
            opponent.pending_invitation = {
                "from": self.nickname,
                "from_elo": self.elo,
                "elo_diff": elo_diff
                }
            opponent.Send({
                "action": "invite_request", 
                "from": self.nickname,
                "from_elo": self.elo,
                "elo_diff": elo_diff,
                "forced": True  # Player must accept
                })
            
    def Network_ovals(self, data: Dict[str, List[Tuple[int, int]]]) -> None:
        """"To check and place a sausage
        
        Args:
            data (dict): Must contain 'ovals' key with list of points"""
            
        if self.status == "playing" and self.opponent:
            points = data["ovals"]

            if len(points) != 3 or len(set(points)) != 3:
                self.Send({"action": "invalid_move", 
                           "message": "You must select exactly 3 different points"
                           })
                return

            for x, y in points:
                if x < 0 or x >= BOARD_WIDTH or y < 0 or y >= BOARD_HEIGHT or (x + y) % 2 != 0:
                    self.Send({"action": "invalid_move", "message": "Invalid position on the board"})
                    return
            
            if not self._server.ValidateSausage(points, self.game_id):
                self.Send({"action": "invalid_move", "message": "Invalid sausage"})
                return
            
            # Update game state
            self._server.games[self.game_id]["sausages"].append(points)
            
            # Notify players
            self.Send({"action": "valid_move", "ovals": points})
            self.opponent.Send({"action": "ovals", "ovals": points})
            
            # Switch turns
            self.Send({"action": "turn_update", "your_turn": False})
            self.opponent.Send({"action": "turn_update", "your_turn": True})
            
            self._server.check_end_game(self.game_id, self)

    def Network_invite_response(self, data: Dict[str, bool]) -> None:
        """"Response to an invitation
        
        Args : True or False"""
        
        if self.pending_invitation:
            opponent = self._server.FindPlayer(self.pending_invitation["from"])
            if opponent and opponent.status == "waiting":
                if data["accept"]:
                    self._start_game_with(opponent)
                else:
                    opponent.Send({
                        "action": "invite_rejected",
                        "message": f"{self.nickname} declined your invitation"
                        })
        self.pending_invitation = None

           
    def _start_game_with(self, opponent: 'ClientChannel') -> None:
        """"To begin a new game"""
        self.status = opponent.status = "playing"
        self.opponent = opponent
        opponent.opponent = self
        self.game_id = opponent.game_id = f"{self.nickname}-{opponent.nickname}"
        
        self._server.games[self.game_id] = {
            "player1": self,
            "player2": opponent,
            "sausages": [],
            "initial_elos": (self.elo, opponent.elo)
        }
        
        # Random choice of the first player
        starter = choice([self, opponent])
        self.Send({
            "action": "start_game",
            "opponent": opponent.nickname,
            "opponent_elo": opponent.elo,
            "your_turn": starter == self
        })
        opponent.Send({
            "action": "start_game",
            "opponent": self.nickname,
            "opponent_elo": self.elo,
            "your_turn": starter == opponent
        })
    
    def Network_game_over(self, data: Dict[str, str]) -> None:
        """To notify the end of the game
        
        Args:
            data (dict): Must contain 'winner' key with nickname
        """
        if self.status == "playing" and self.opponent:
            winner_nick = data["winner"]
            game = self._server.games.get(self.game_id)
            
            if game:
                player1, player2 = game["player1"], game["player2"]
                elo1, elo2 = game["initial_elos"]
                
                if winner_nick == player1.nickname:
                    delta = min(MAX_ELO_DIFFERENCE, elo1 - elo2)
                    points = BASE_ELO_POINTS + delta // 3
                    player1.elo += points
                    player2.elo -= points
                else:
                    delta = min(MAX_ELO_DIFFERENCE, elo2 - elo1)
                    points = BASE_ELO_POINTS + delta // 3
                    player2.elo += points
                    player1.elo -= points
                
                player1.Send({
                    "action": "elo_update",
                    "new_elo": player1.elo,
                    "elo_change": (points if winner_nick == player1.nickname else -points)
                })
                player2.Send({
                    "action": "elo_update",
                    "new_elo": player2.elo,
                    "elo_change": (points if winner_nick == player2.nickname else -points)
                })
                
                self._server.EndGame(self.game_id, winner_nick)
    
    def Network_player_quit(self, data: Dict[str, Any]) -> None:
        """To notify if someone quits or disconnects form the board"""
        if self.status == "playing" and self.opponent:
            self.opponent.Send({"action": "opponent_disconnected"})
            self._server.EndGame(self.game_id, self.opponent.nickname)
        
        self.status = "waiting"
        self.opponent = None
        self.game_id = None
        self._server.UpdateLobby()

class MyServer(Server):
    """Main server class handling all connections and game management."""
    
    channelClass = ClientChannel
    
    def __init__(self, mylocaladdr):
        Server.__init__(self, localaddr=mylocaladdr)
        self.players = [] # List of connected players
        self.games = {} # Dic of the active games
        print('Server launched')
    
    def Connected(self, channel: ClientChannel, addr: Tuple[str, int]) -> None:
        """Called if a new player connects"""
        self.AddPlayer(channel)
    
    def AddPlayer(self, player: ClientChannel) -> None:
        """Add new player to the server.
        
        Args:
            player (ClientChannel): The player to add
        """
        print(f"New Player connected: {player.nickname}")
        self.players.append(player)
        self.UpdateLobby()
    
    def DelPlayer(self, player: ClientChannel) -> None:
        """Remove players who quits the lobby
        
        Args:
            player (ClientChannel): The player to remove
        """
        print(f"Deleting Player {player.nickname}")
        if player.status == "playing" and player.opponent:
            player.opponent.Send({"action": "opponent_disconnected"})
            self.EndGame(player.game_id, player.opponent.nickname)
        if player in self.players:
            self.players.remove(player)
        self.UpdateLobby()
    
    def FindPlayer(self, nickname: str) -> Optional[ClientChannel]:
        """"Find player nickname
        
        Args:
            nickname (str): The nickname to search for
            
        Returns:
            ClientChannel or None: The player if found, else None
        """
        for player in self.players:
            if player.nickname == nickname:
                return player
        return None
    
    def UpdateLobby(self):
        """Send updated player list to all clients"""
        waiting_players = sorted(
            [
                {"name": p.nickname, "elo": p.elo} 
                for p in self.players 
                if p.status == "waiting"
            ],
            key=lambda x: x["elo"],
            reverse=True  # Sort by ELO (highest first)
            )
        for p in self.players:
            p.Send({
                "action": "lobby_update",
                "players": waiting_players
            })
    
    def ValidateSausage(self, points: List[Tuple[int, int]], game_id: str) -> bool:
        """Validate if sausage placement is legal.
       
       Args:
           points (list): List of (x,y) tuples
           game_id (str): The game ID
           
       Returns:
           bool: True or False
       """
        # Number of points selected
        if len(points) != 3 or len(set(points)) != 3:
            return False
        
        # If the points are on the grid
        for x, y in points:
            if (not (0 <= x < BOARD_WIDTH) or 
                not (0 <= y < BOARD_HEIGHT) or 
                (x + y) % 2 != 0):
                return False
    
        # Check the distance rule (<=2 in row and <=2 in columns)
        for i in range(3):
            p1 = points[i]
            connected = False
            for j in range(3):
                if i == j:
                    continue
                p2 = points[j]
                dx = abs(p1[0] - p2[0])
                dy = abs(p1[1] - p2[1])
                if dx <= MAX_DISTANCE and dy <= MAX_DISTANCE:
                    connected = True
                    break
            if not connected:
                return False
            
        # Check sausage crossing    
        game = self.games.get(game_id)
        if game:
            for sausage in game["sausages"]:
                if self.CheckCrossing(points, sausage):
                    return False
    
        return True
    

    def ValidateSausageSimulated(self, points: List[Tuple[int, int]], game: Dict[str, Any]) -> bool:
        """Validation without sending messages (for end game check)
        
        Args and returns : same as the previous function : ValidateSausage()"""
        if len(points) != 3 or len(set(points)) != 3:
            return False
        
        # Check distance rule
        for i in range(3):
            for j in range(i + 1, 3):
                x1, y1 = points[i]
                x2, y2 = points[j]
                if abs(x1 - x2) > MAX_DISTANCE or abs(y1 - y2) > MAX_DISTANCE:
                    return False

        # Vérifie les croisements
        for sausage in game["sausages"]:
            if self.CheckCrossing(points, sausage):
                return False

        return True
    

    def CheckCrossing(self, sausage1: List[Tuple[int, int]], sausage2: List[Tuple[int, int]]) -> bool:
        """Check if two sausages intersect.
        
        Args:
            sausage1 (list): First sausage points
            sausage2 (list): Second sausage points
            
        Returns:
            bool: True or False
        """
        if set(sausage1) & set(sausage2):
            return True
    
        # Check each segment of sausage1 against each segment of sausage2
        for i in range(3):
            p1 = sausage1[i]
            p2 = sausage1[(i+1)%3]
        
            for j in range(3):
                p3 = sausage2[j]
                p4 = sausage2[(j+1)%3]
                
                if self.segments_intersect(p1, p2, p3, p4):
                    return True
    
        return False

    def segments_intersect(self, p1: Tuple[int, int], p2: Tuple[int, int], p3: Tuple[int, int], p4: Tuple[int, int]) -> bool:
        """Check if two line segments intersect"""
        # https://stackoverflow.com/questions/63398960
        
        def ccw(A, B, C):
            """"Determines whether the turn from point A->B->C is counter-clockwise.
                The result is based on the sign of the cross product (B-A) × (C-A).
        

                True if the points are in counter-clockwise order,
                False if collinear or clockwise"""
                
            return (C[1]-A[1])*(B[0]-A[0]) > (B[1]-A[1])*(C[0]-A[0])
    
        A, B = p1, p2
        C, D = p3, p4
        
        # The segments intersect if:
        # 1. Points p1,p2 are on opposite sides of the line p3-p4 (first condition)
        # AND
        # 2. Points p3,p4 are on opposite sides of the line p1-p2 (second condition)
    
        return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)
    
    def check_end_game(self, game_id: Dict[str, Any], last_player: ClientChannel) -> None:
        """Check if game should end (no possible moves left).
        
        Args:
            game_id (str): The game identifier
            last_player (ClientChannel): The player who made last move
        """
        game = self.games.get(game_id)
        if not game:
            return
        
        # Get all occupied points
        occupied = set()
        for sausage in game["sausages"]:
            occupied.update(sausage)

        # Get all valid remaining points
        valid_points = [
            (col, row)
            for col in range(BOARD_WIDTH)
            for row in range(BOARD_HEIGHT)
            if (col + row) % 2 == 0 and (col, row) not in occupied
        ]
        
        # Check if any valid sausage can still be placed
        for trio in combinations(valid_points, 3):
            if self.ValidateSausageSimulated(list(trio), game):
                return  # At least one valid move remains
        
        # No valid moves left - end game
        self.EndGame(str(game_id), winner=last_player.nickname)
    
    def EndGame(self, game_id: str, winner: str) -> None:
        """Clean up after game ends and update ELOs.
        
        Args:
            game_id (str): The game identifier
            winner (str): Nickname of the winning player
        """
        if game_id in self.games:
            game = self.games[game_id]
            player1 = game["player1"]
            player2 = game["player2"]
            nickname1 = player1.nickname
            nickname2 = player2.nickname
            elo1, elo2 = game["initial_elos"]

            # Calculate ELO changes
            if winner == nickname1:
                delta = min(MAX_ELO_DIFFERENCE, elo1 - elo2)
                points = BASE_ELO_POINTS + delta // 3
                player1.elo += points
                player2.elo -= points
            else:
                delta = min(MAX_ELO_DIFFERENCE, elo2 - elo1)
                points = BASE_ELO_POINTS + delta // 3
                player2.elo += points
                player1.elo -= points

            # Send ELO updates
            player1.Send({
                "action": "elo_update",
                "new_elo": player1.elo,
                "elo_change": (points if winner == nickname1 else -points)
                })
            player2.Send({
                "action": "elo_update",
                "new_elo": player2.elo,
                "elo_change": (points if winner == nickname2 else -points)
                })

            # Announce winner
            player1.Send({"action": "game_over", "winner": winner})
            player2.Send({"action": "game_over", "winner": winner})

            # Reset player states
            player1.status = "waiting"
            player2.status = "waiting"
            player1.opponent = None
            player2.opponent = None
            del self.games[game_id]

            self.UpdateLobby()
    
    def Launch(self):
        while True:
            self.Pump()
            sleep(0.001)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Please use: python3", sys.argv[0], "host:port")
        print("e.g., python3", sys.argv[0], "localhost:31425")
        host, port = "localhost", "31425"
    else:
        host, port = sys.argv[1].split(":")
    s = MyServer((host, int(port)))
    s.Launch()