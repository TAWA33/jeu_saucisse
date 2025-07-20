from typing import List, Tuple, Dict, Set, Optional, Union, Any

import sys
from time import sleep
from sys import stdin, exit
from tkinter import *
from tkinter import messagebox
import re

from PodSixNet.Connection import connection, ConnectionListener

MAX_ELO_DIFFERENCE = 300

COLUMNS = 9
ROWS = 7

MAX_DISTANCE = 2

CELL_SIZE = 70
WIDTH_PLATEAU = COLUMNS * CELL_SIZE
HEIGHT_PLATEAU = ROWS * CELL_SIZE
RADIUS=15

INITIAL = 0
LOBBY = 1
PLAYING = 2
GAME_OVER = 3

LOBBY_BG = "midnight blue"
LOBBY_FG = "white"
LOBBY_BTN = "DeepSkyBlue3"

BG_COLOR = "GRAY76"
NODE_COLOR = "steel blue"
NODE_OUTLINE = "blue"

MY_COLOR = "darkorange"
OPPONENT_COLOR = "darkviolet"

INVALID_NODE = "SteelBlue4" 

class Client(ConnectionListener):
    def __init__(self, host: str, port: Union[str, int], window: 'ClientWindow') -> None:
        self.window = window
        self.Connect((host, port))
        self.state = INITIAL
        self.elo = 1000
        self.nickname = ""
        self.opponent_name = ""
        print("Client started")
        print("Ctrl-C to exit the lobby")
        print("Enter your nickname: ")
        nickname = stdin.readline().rstrip("\n")
        self.nickname = nickname
        connection.Send({"action": "nickname", "nickname": nickname})
    
    def quit_client(self) -> None:
        """Procedure if a client quit the board. Redirected to the lobby
            or Quit if the client is in the lobby"""
        if self.state == PLAYING:
            connection.Send({"action": "player_quit"})
            connection.Pump()
            self.state = LOBBY
            self.window.reset_game()
        elif self.state == LOBBY:
            connection.Close()
            self.window.quit()
    
    def Network_connected(self, data: Dict[str, Any]) -> None:
        print("You are now connected to the server")
        self.state = LOBBY
    
    def Network_lobby_update(self, data: Dict[str, Any]) -> None:
        """Update lobby player list."""
        self.window.update_lobby(data["players"])
        
    def Network_invite_request(self, data: Dict[str, Any]) -> None:
        """"Response to an incoming game invitation."""
        if data.get("forced", False):
            self.window.show_invitation_popup(
                data["from"],
                data["from_elo"],
                data["elo_diff"],
                forced=True
                )
            self.Send({"action": "invite_response", "accept": True})
        else:
            self.window.show_invitation_popup(
                data["from"],
                data["from_elo"],
                data["elo_diff"],
                forced=False
                )

    def Network_invite_error(self, data: Dict[str, Any]) -> None:
        messagebox.showerror("Invitation Error", data["message"])

    def Network_invite_rejected(self, data: Dict[str, Any]) -> None:
        messagebox.showinfo("Invitation Declined", "The player declined your invitation")
    
    def Network_elo_update(self, data: Dict[str, Any]) -> None:
        """Update ELO rating display."""
        self.elo = data["new_elo"]
        change = data["elo_change"]
        self.window.elo_label.config(text=f"Your ELO: {self.elo} ({change:+})")
        messagebox.showinfo(
            "ELO Updated",
            f"New ELO: {self.elo}\n"
            f"Change: {change:+}"
        )
    
    def Network_start_game(self, data: Dict[str, Any]) -> None:
        """Initialize game start."""
        self.state = PLAYING
        your_turn = data.get("your_turn", False)
        self.opponent_name = data["opponent"]
        self.window.start_game(data["opponent"], data["your_turn"], your_turn)
    
    def Network_ovals(self, data: Dict[str, Any]) -> None:
        """Draw opponent's sausage"""
        points = data["ovals"]
        self.window.draw_opponent_move(points)
        
    def Network_turn_update(self, data: Dict[str, Any]) -> None:
        """Update turn indicator."""
        self.window.update_turn(data["your_turn"])
        
    def Network_valid_move(self, data: Dict[str, Any]) -> None:
        """Confirmation and draw client's sausage"""
        points = data["ovals"]
        self.window.draw_valid_move(points)
        self.window.reset_selection()
            
    
    def Network_invalid_move(self, data: Dict[str, Any]) -> None:
        """Notify the player that his sausage is invalid"""
        messagebox.showerror("Invalid Move", "This sausage is not valid!")
        self.window.reset_selection() 
    
    def Network_game_over(self, data: Dict[str, Any]) -> None:
        """Notify the end of the game"""
        self.state = GAME_OVER
        winner = data["winner"]
        messagebox.showinfo("Game Over", f"{winner} won the game!")
        self.window.reset_game()
    
    def Network_opponent_disconnected(self, data: Dict[str, Any]) -> None:
        """If the opponent disconnects"""
        messagebox.showerror("Opponent Disconnected", "Your opponent has disconnected")
        self.state = LOBBY
        self.window.reset_game()
    
    def Loop(self):
        connection.Pump()
        self.Pump()

class ClientWindow(Tk):
    def __init__(self, host, port):
        Tk.__init__(self)
        self.title("Sausage Game - Lobby")
        self.client = Client(host, int(port), self)
        self.protocol("WM_DELETE_WINDOW", lambda: self.exit_game())
        
        # Lobby Frame
        self.lobby_frame = Frame(self, bg=LOBBY_BG)
        self.elo_label = Label(self.lobby_frame, bg=LOBBY_BG, fg=LOBBY_FG, text=f"Your ELO: 1000")
        self.elo_label.pack(pady=5)
        self.players_list = Listbox(self.lobby_frame, bg=LOBBY_BG, fg=LOBBY_FG, height=10, width=30, highlightthickness=0)
        self.invite_button = Button(self.lobby_frame, bg=LOBBY_BTN, fg=LOBBY_FG, text="Invite", command=self.invite_player)
        self.status_label = Label(self.lobby_frame, bg=LOBBY_BG, fg=LOBBY_FG, text="Select a player to invite")
        
        self.players_list.pack(pady=10)
        self.invite_button.pack(pady=5)
        self.status_label.pack()
        self.lobby_frame.pack()
        
        # Gale Frame
        self.game_frame = Frame(self, bg=BG_COLOR)
        self.white_board_canvas = Canvas(self.game_frame, width=WIDTH_PLATEAU, height=HEIGHT_PLATEAU, bg=BG_COLOR, highlightthickness=0)
        self.turn_label = Label(self.game_frame, bg=BG_COLOR, text="", font=('Helvetica', 14))
        
        self.white_board_canvas.pack(pady=10)
        self.turn_label.pack()
        
        Button(self.game_frame, text='Quit', command=self.exit_game).pack(side=BOTTOM, pady=10)
        
        self.selected_points = []
        self.occupied_points = set()
        self.client.occupied_points = self.occupied_points
        self.current_turn = False
        
        self.init_board()
        
    
    
    def init_board(self) -> None:
        """Initialize game board with clickable points."""
        for col in range(COLUMNS):
            for row in range(ROWS):
                if (col + row) % 2 == 0:
                    x = col * CELL_SIZE + CELL_SIZE//2
                    y = row * CELL_SIZE + CELL_SIZE//2
                    btn_tag = f"btn_{col}_{row}"
                    self.white_board_canvas.create_oval(
                        x-RADIUS, y-RADIUS, x+RADIUS, y+RADIUS,
                        fill=NODE_COLOR, outline=NODE_OUTLINE, width=2,
                        tags=btn_tag
                    )
                    self.white_board_canvas.tag_bind(btn_tag, "<Button-1>", 
                                                   lambda event, col=col, row=row: self.onOvalClick(col, row))
    
    
    def show_invitation_popup(self, from_player: str, from_elo: int, elo_diff: int, forced: bool):
        """Show invitation dialog."""
        popup = Toplevel(self, bg=LOBBY_BG)
        popup.title("Invitation Received")
        popup.geometry("400x200")
        popup.resizable(False, False)

        self.protocol("WM_DELETE_WINDOW", lambda: self.exit_game())
    
        Label(popup, bg=LOBBY_BG, fg=LOBBY_FG, text=f"{from_player} invites you to play", 
              font=('Helvetica', 12, 'bold')).pack(pady=10)
        Label(popup, bg=LOBBY_BG, fg=LOBBY_FG, text=f"ELO: {from_elo} | Difference: {elo_diff}", 
              font=('Helvetica', 10)).pack()

        btn_frame = Frame(popup, bg=LOBBY_BG)
        btn_frame.pack(pady=20)

        accept_btn = Button(btn_frame, text="Accept", fg='white', bg="#4CAF50",
           command=lambda: self.respond_to_invitation(popup, True),
           font=('Helvetica', 10, 'bold'), width=10)
        accept_btn.pack(side=LEFT, padx=10)

        refuse_btn = Button(btn_frame, text="Decline", fg="white", bg="#F44336",
           command=lambda: self.respond_to_invitation(popup, False),
           font=('Helvetica', 10, 'bold'), width=10)
        refuse_btn.pack(side=LEFT, padx=10)

        popup.transient(self)
        popup.grab_set()
        self.wait_window(popup)

    def respond_to_invitation(self, popup, accepted):
        """Send response to invitation."""
        popup.destroy()
        self.client.Send({
            "action": "invite_response", 
            "accept": accepted
            })
    
    def update_lobby(self, players_data):
        """Update lobby player list display."""
        self.players_list.delete(0, END)
        for i, player in enumerate(players_data):
            if player["name"] != self.client.nickname:
                rank = i + 1
                name = player["name"]
                elo = player["elo"]
                elo_diff = abs(self.client.elo - elo)
                text = f"#{rank} {name} (ELO: {elo})"
                self.players_list.insert(END, text)

                color = LOBBY_FG

                # Podium colors
                if rank == 1:
                    color = "gold"
                elif rank == 2:
                    color = "silver"
                elif rank == 3:
                    color = "brown"
            
                # Large ELO difference - red (except for podium)
                if elo_diff > MAX_ELO_DIFFERENCE and rank > 3:
                    color = "red"

                self.players_list.itemconfig(END, fg=color)
    
    def invite_player(self):
        """Send game invitation to selected player."""
        selection = self.players_list.curselection()
        if selection:
            selected_text = self.players_list.get(selection[0])
        
            # Extract player name using regex
            match = re.search(r"#\d+\s+(.+?)\s+\(ELO", selected_text)
            if match:
                opponent = match.group(1)
                self.client.Send({"action": "invite", "opponent": opponent})
                self.status_label.config(text=f"Invitation sent to {opponent}")
            else:
                self.status_label.config(text="Error: Could not send invitation")
    
    def start_game(self, opponent, opponent_elo, your_turn):
        """Initialize game view."""
        self.lobby_frame.pack_forget()
        self.game_frame.pack()
        self.title(f"Sausage Game - VS - {opponent} ") #(ELO: {opponent_elo})
        self.opponent_name = opponent
        self.update_turn(your_turn)
    
    def reset_game(self):
        """Reset game to lobby state."""
        self.game_frame.pack_forget()
        self.lobby_frame.pack()
        self.title("Sausage Game - Lobby")
        self.selected_points = []
        self.occupied_points = set()
        self.white_board_canvas.delete("line")
        self.init_board()
    
    def reset_selection(self):
        """Reset current node selection."""
        for col, row in self.selected_points:
            if (col, row) not in self.occupied_points:
                self.white_board_canvas.itemconfig(f"btn_{col}_{row}", fill=NODE_COLOR)
        self.white_board_canvas.delete("temp_line")
        self.selected_points = []
    
    def onOvalClick(self, col: int, row: int) -> None:
        """Procedure if points are selected"""
        if not self.current_turn:
            return
    
        if (col, row) in self.occupied_points:
            self.show_error_message("Point already used!")
            return
    
        if (col, row) not in self.selected_points:
            if len(self.selected_points) >= 3:
                self.reset_selection()
                return
                
            self.selected_points.append((col, row))
            self.white_board_canvas.itemconfig(f"btn_{col}_{row}", fill=MY_COLOR)
            

            if len(self.selected_points) >= 2:
                self.white_board_canvas.delete("temp_line")
                self.drawConnectingLines(self.selected_points, MY_COLOR, temporary=True)
            
            if len(self.selected_points) == 3:
                if self.validate_local_sausage(self.selected_points):
                    connection.Send({
                        "action": "ovals",
                        "ovals": self.selected_points
                        })
                else:
                    self.show_error_message("The distance between all points must be <= 2")
                    self.reset_selection()
    
    def validate_local_sausage(self, points: List[Tuple[int, int]]) -> bool:
        """Validate sausage locally before sending to server."""
        if len(points) != 3 or len(set(points)) != 3:
            return False
        for i in range(3):
            x1, y1 = points[i]
            x2, y2 = points[(i+1)%3]
            if abs(x1 - x2) > MAX_DISTANCE or abs(y1 - y2) > MAX_DISTANCE:
                return False
        return True


    def draw_valid_move(self, points: List[Tuple[int, int]]) -> None:
        """Display valid sausage permanently."""
        self.white_board_canvas.delete("temp_line")
        
        for (col, row) in points:
            self.occupied_points.add((col, row))
            self.white_board_canvas.itemconfig(f"btn_{col}_{row}", fill=MY_COLOR)
        
        self.drawConnectingLines(points, MY_COLOR, temporary=False)
        
        self.selected_points = []
    
    def drawConnectingLines(self, points: List[Tuple[int, int]], color: str, temporary: bool = False) -> None:
        """Draw lines connecting sausage points."""
        if len(points) < 2:
            return
        
        line_tag = "temp_line" if temporary else "line"
        
        # Case for 2 points - draw a single line
        if len(points) == 2:
            p1, p2 = points
            x1, y1 = p1[0] * CELL_SIZE + CELL_SIZE//2, p1[1] * CELL_SIZE + CELL_SIZE//2
            x2, y2 = p2[0] * CELL_SIZE + CELL_SIZE//2, p2[1] * CELL_SIZE + CELL_SIZE//2
            
            self.white_board_canvas.create_line(
                x1, y1, x2, y2,
                fill=color, width=2, tags=line_tag
            )
            return
        
        # Case for 3 points - draw a triangle (two shortest sides)
        if len(points) == 3:
            segments = []
            for i in range(3):
                p1 = points[i]
                p2 = points[(i+1)%3]
                dx = abs(p1[0] - p2[0])
                dy = abs(p1[1] - p2[1])
                length = dx*dx + dy*dy
                segments.append((length, p1, p2))
            
            # Draw the two shorter sides of the triangle
            segments.sort()
            
            for length, p1, p2 in segments[:2]:
                x1, y1 = p1[0] * CELL_SIZE + CELL_SIZE//2, p1[1] * CELL_SIZE + CELL_SIZE//2
                x2, y2 = p2[0] * CELL_SIZE + CELL_SIZE//2, p2[1] * CELL_SIZE + CELL_SIZE//2
                
                self.white_board_canvas.create_line(
                    x1, y1, x2, y2,
                    fill=color, width=2, tags=line_tag
                )
    
    def draw_opponent_move(self, points: List[Tuple[int, int]]) -> None:
        """Display opponent's move."""
        for (col, row) in points:
            self.occupied_points.add((col, row))
            self.white_board_canvas.itemconfig(f"btn_{col}_{row}", fill=OPPONENT_COLOR)
        self.drawConnectingLines(points, OPPONENT_COLOR, temporary=False)
    
    def update_turn(self, your_turn: bool) -> None:
        """Update turn indicator."""
        self.current_turn = your_turn
        if your_turn:
            self.turn_label.config(text="Your turn!", fg="green")
            self.reset_selection()
        else:
            self.turn_label.config(text=f"{self.opponent_name}'s turn", fg="red")
            
    
    def show_error_message(self, message: str) -> None:
        """Display temporary error message."""
        self.white_board_canvas.delete("error_msg")
        self.white_board_canvas.create_text(
            WIDTH_PLATEAU//2, 20,
            text=message,
            fill="red",
            font=('Helvetica', 12, 'bold'),
            tags="error_msg"
            )
        self.after(2000, lambda: self.white_board_canvas.delete("error_msg")) 
    
    
    def exit_game(self):
        """Notify the client how to exit the lobby"""
        print("Ctrl-C to exit the lobby")
        self.client.quit_client()
    
    def myMainLoop(self):
        while True:
            self.update()
            self.client.Loop()
            sleep(0.001)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Please use: python3", sys.argv[0], "host:port")
        print("e.g., python3", sys.argv[0], "localhost:31425")
        host, port = "localhost", "31425"
    else:
        host, port = sys.argv[1].split(":")
    client_window = ClientWindow(host, port)
    try:
        client_window.myMainLoop()
    except KeyboardInterrupt:
        pass
    finally:
        client_window.destroy()