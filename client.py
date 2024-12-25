import sys
import pickle
import socket
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem, QGridLayout
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

        self.name = ''

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


class RegistrationWindow(QWidget):
    def __init__(self, client: Client):
        super().__init__()
        self.client = client
        self.client.update_signal.connect(self.handle_server_message)

        self.main_window = None

        self.setWindowTitle('registration')
        self.setGeometry(300, 300, 250, 120)
        layout = QVBoxLayout()
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText('enter your name')

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText('enter password')

        send = QPushButton('send')
        layout.addWidget(self.input_name)
        layout.addWidget(self.input_password)
        layout.addWidget(send)

        self.setLayout(layout)

        send.clicked.connect(self.send)

        self.show()

    def send(self):
        name = self.input_name.text()
        password = self.input_password.text()
        if name and password:
            self.client.send({'command': 'registration', 'name': name, 'password': password})

    def handle_server_message(self, message):
        if message["type"] == "registration":
            if message['message'] == 'ok':
                self.hide()
                self.client.name = self.input_name.text()
                self.main_window = MainWindow(self.client)
            elif message['message'] == 'no':
                self.input_password.setText('')
                self.input_password.setPlaceholderText('enter CORRECT password')


# GUI Code
class MainWindow(QMainWindow):
    def __init__(self, client: Client):
        super().__init__()
        self.client = client
        self.client.update_signal.connect(self.handle_server_message)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"Anagrams Game. {self.client.name}")
        self.setGeometry(100, 100, 600, 400)

        self.central_widget = QWidget()
        self.layout = QVBoxLayout()

        self.grid = QGridLayout()

        self.info_label = QLabel(f"Welcome to Anagrams, {self.client.name}!")
        self.layout.addWidget(self.info_label)

        self.room_input = QLineEdit()
        # self.room_input.editingFinished.connect(self.join_room)
        self.room_input.setPlaceholderText("Enter room name")
        self.layout.addWidget(self.room_input)

        self.create_button = QPushButton("Create Room")
        self.create_button.clicked.connect(self.create_room)
        # self.layout.addWidget(self.create_button)

        self.join_button = QPushButton("Join Room")
        self.join_button.clicked.connect(self.join_room)
        # self.layout.addWidget(self.join_button)

        self.grid.addWidget(self.create_button, 3, 0, 1, 1)
        self.grid.addWidget(self.join_button, 3, 1, 1, 1)

        self.layout.addLayout(self.grid)

        self.start_button = QPushButton("Start Game")
        self.start_button.clicked.connect(self.start_game)
        self.layout.addWidget(self.start_button)

        self.word_label = QLabel("Current Word: -")
        self.layout.addWidget(self.word_label)

        self.word_input = QLineEdit()
        # self.word_input.editingFinished.connect(self.submit_word)
        self.word_input.setPlaceholderText("Enter your word")
        self.layout.addWidget(self.word_input)

        self.submit_button = QPushButton("Submit Word")
        self.submit_button.clicked.connect(self.submit_word)
        self.layout.addWidget(self.submit_button)

        self.score_table = QTableWidget()
        self.score_table.setColumnCount(2)
        self.score_table.setHorizontalHeaderLabels(["Player", "Score"])
        self.layout.addWidget(self.score_table)

        self.exit_button = QPushButton('exit')
        self.exit_button.clicked.connect(self.exit)
        self.layout.addWidget(self.exit_button)

        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)

        self.show()

    def create_room(self):
        room_name = self.room_input.text()
        if room_name:
            self.client.send({"command": "create_room", "room": room_name})

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
            self.client.send({"command": "submit_word", "room": room_name, "word": word, "player": self.client.name})
            self.word_input.clear()

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

    def exit(self):
        self.client.send({"command": "exit"})
        self.client.disconnect()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Start client and GUI
    client_ex = Client(HOST, PORT)
    client_ex.client_connect()

    window = RegistrationWindow(client_ex)
    window.show()

    sys.exit(app.exec())