import sys
import pickle
# import random
import socket
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import pyqtSignal, QObject


HOST = '127.0.0.1'
PORT = 65432


class Client(QObject):
    update_signal = pyqtSignal(dict)

    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False

    def client_connect(self):
        try:
            self.socket.connect((self.host, self.port))
            self.connected = True
            threading.Thread(target=self.listen_to_server, daemon=True).start()
        except Exception as e:
            print(f"Connection error: {e}")

    def send(self, message):
        try:
            self.socket.sendall(pickle.dumps(message))
        except Exception as e:
            print(f"Send error: {e}")

    def listen_to_server(self):
        while self.connected:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break
                message = pickle.loads(data)
                self.update_signal.emit(message)
            except Exception as e:
                print(f"Receive error: {e}")
                break

    def disconnect(self):
        self.connected = False
        self.socket.close()


# GUI Code
class MainWindow(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.client.update_signal.connect(self.handle_server_message)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Anagrams Game")
        self.setGeometry(100, 100, 600, 400)

        self.central_widget = QWidget()
        self.layout = QVBoxLayout()

        self.info_label = QLabel("Welcome to Anagrams!")
        self.layout.addWidget(self.info_label)

        self.room_input = QLineEdit()
        self.room_input.setPlaceholderText("Enter room name")
        self.layout.addWidget(self.room_input)

        self.join_button = QPushButton("Join Room")
        self.join_button.clicked.connect(self.join_room)
        self.layout.addWidget(self.join_button)

        self.start_button = QPushButton("Start Game")
        self.start_button.clicked.connect(self.start_game)
        self.layout.addWidget(self.start_button)

        self.word_label = QLabel("Current Word: -")
        self.layout.addWidget(self.word_label)

        self.word_input = QLineEdit()
        self.word_input.setPlaceholderText("Enter your word")
        self.layout.addWidget(self.word_input)

        self.submit_button = QPushButton("Submit Word")
        self.submit_button.clicked.connect(self.submit_word)
        self.layout.addWidget(self.submit_button)

        self.score_table = QTableWidget()
        self.score_table.setColumnCount(2)
        self.score_table.setHorizontalHeaderLabels(["Player", "Score"])
        self.layout.addWidget(self.score_table)

        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)

    def join_room(self):
        room_name = self.room_input.text()
        if room_name:
            self.client.send({"command": "join_room", "room": room_name})

    def start_game(self):
        room_name = self.room_input.text()
        if room_name:
            self.client.send({"command": "start_game", "room": room_name})

    def submit_word(self):
        word = self.word_input.text()
        room_name = self.room_input.text()
        if word and room_name:
            self.client.send({"command": "submit_word", "room": room_name, "word": word, "player": "Player1"})

    def handle_server_message(self, message):
        if message["type"] == "info":
            self.info_label.setText(message["message"])
        elif message["type"] == "start":
            self.word_label.setText(f"Current Word: {message['word']}")
        elif message["type"] == "score":
            self.update_score_table(message["scores"])

    def update_score_table(self, scores):
        self.score_table.setRowCount(len(scores))
        for i, (player, score) in enumerate(scores.items()):
            self.score_table.setItem(i, 0, QTableWidgetItem(player))
            self.score_table.setItem(i, 1, QTableWidgetItem(str(score)))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # # Start server in a separate thread
    # server = GameServer(HOST, PORT)
    # threading.Thread(target=server.start, daemon=True).start()

    # Start client and GUI
    client = Client(HOST, PORT)
    client.client_connect()

    window = MainWindow(client)
    window.show()

    sys.exit(app.exec())