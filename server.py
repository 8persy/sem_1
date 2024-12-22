from collections import Counter
import pickle
import random
import socket
import threading
# from PyQt6.QtWidgets import (
#     QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
#     QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem
# )
# from PyQt6.QtCore import pyqtSignal, QObject

# Constants
HOST = '127.0.0.1'
PORT = 65432


class Room:
    def __init__(self, name: str):
        self.name = name
        self.clients = []  # type: [socket.socket]
        self.name = []  # type: [str]

    def room_broadcast(self, msg):
        for client in self.clients:
            client.sendall(pickle.dumps({"type": "start", "word": msg}))

    def remove_client(self, client):
        if client in self.clients:
            self.clients.remove(client)


# Server Code
class GameServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.clients = []  # type: [socket.socket] # List of connected clients
        self.rooms = {}  # type: {str: list[socket.socket]} # {room_name: [clients]}
        self.dataset = ["example", "python", "pickle", "thread", "socket", "server"]
        self.scores = {}  # type: {str: int} # {client_name: score}
        self.current_words = {}  # type: {str: str} # {room_name: current_word}
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Server started on {self.host}:{self.port}")

    @staticmethod
    def check_word(reference, word):
        word_counter = Counter(word)
        reference_counter = Counter(reference)
        print(word_counter)
        print(reference_counter)

        for letter, count in word_counter.items():
            if count > reference_counter.get(letter, 0):
                print(count, letter)
                print(reference_counter.get(letter, 0))
                print("error")
                return False

        return True

    def broadcast(self, message, room):
        """Send a message to all clients in the room."""
        for client in self.rooms.get(room, []):
            try:
                client.sendall(pickle.dumps(message))
            except Exception as e:
                print(f"Error broadcasting to {client}: {e}")

    def handle_client(self, client, address):
        """Handle a single client."""
        print(f"New connection from {address}")
        try:
            while True:
                data = client.recv(1024)
                if not data:
                    break
                message = pickle.loads(data)
                command = message.get("command")

                if command == "join_room":
                    room = message["room"]
                    self.rooms.setdefault(room, []).append(client)
                    self.broadcast({"type": "info", "message": f"{address} joined {room}"}, room)

                elif command == "start_game":
                    room = message["room"]
                    word = random.choice(self.dataset)
                    self.current_words[room] = word
                    self.broadcast({"type": "start", "word": word}, room)

                elif command == "submit_word":
                    room = message["room"]
                    player = message["player"]
                    word = message["word"]

                    if self.check_word(word=word, reference=self.current_words[room]):
                        self.scores[player] = self.scores.get(player, 0) + 1
                        self.broadcast({"type": "score", "scores": self.scores}, room)

        except Exception as e:
            print(f"Error with client {address}: {e}")
        finally:
            print(f"Closing connection with {address}")
            client.close()

    def start(self):
        """Start the server and handle incoming connections."""
        try:
            while True:
                client, address = self.server_socket.accept()
                self.clients.append(client)
                threading.Thread(target=self.handle_client, args=(client, address), daemon=True).start()
        except KeyboardInterrupt:
            print("Shutting down server.")
        finally:
            self.server_socket.close()


# Client Code

# Main Execution
if __name__ == "__main__":
    # app = QApplication(sys.argv)

    # Start server in a separate thread
    server = GameServer(HOST, PORT)
    threading.Thread(target=server.start).start()

    # Start client and GUI
    # client = Client(HOST, PORT)
    # client.connect()
    #
    # window = MainWindow(client)
    # window.show()

    # sys.exit(app.exec())
