from collections import Counter
import pickle
import random
import socket
import threading
from threading import Lock
from words import Words
# Constants
HOST = '127.0.0.1'
PORT = 65432


class Room:
    def __init__(self, name: str):
        self.name = name
        self.clients = []  # type: [socket.socket]
        self.names = []  # type: [str]
        self.words_history = []  # type: [str]

    def room_broadcast(self, msg_type: str, msg2_type: str, msg: str):
        for client in self.clients:
            client.sendall(pickle.dumps({"type": msg_type, msg2_type: msg}))

    def is_correct_word(self, word: str):
        if word in self.words_history:
            return False
        return True

    def add_client(self, client: socket.socket, name: str):
        self.clients.append(client)
        self.names.append(name)

    def remove_client(self, client: socket.socket, name: str):
        if client in self.clients:
            self.clients.remove(client)
            self.names.remove(name)
            self.room_broadcast(msg_type='info', msg2_type='message', msg=f'player {name} left game')


# Server Code
class GameServer:
    def __init__(self, host, port):
        # connection
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        # for thread
        self.lock = Lock()

        # clients
        self.names_passwords = {}  # type: {str: str} # {name: password}
        self.clients = []  # type: [socket.socket] # List of connected clients
        self.clients_with_name = {}  # type: {socket.socket: str} # {soket: name}

        # rooms
        self.rooms = []  # type: [Room] # {room_name: [clients]}

        # data of words
        words = Words()
        self.dataset = words.words
        self.current_words = {}  # type: {str: str} # {room_name: current_word}

        # for tables or scores
        self.scores = {}  # type: {str: int} # {client_name: score}

        print(f"Server started on {self.host}:{self.port}")

    @staticmethod
    def check_word(reference, word):
        word_counter = Counter(word)
        reference_counter = Counter(reference)

        for letter, count in word_counter.items():
            if count > reference_counter.get(letter, 0):
                return False

        return True

    def handle_client(self, client: socket.socket, address):
        """Handle a single client."""
        client_name = ''
        room = None
        print(f"New connection from {address}")
        try:
            while True:
                data = client.recv(1024)
                if not data:
                    break
                message = pickle.loads(data)
                command = message.get("command")

                if command == 'registration':
                    client_name = message['name']
                    client_password = message['password']
                    data_password = self.names_passwords.get(client_name, '')
                    if data_password:
                        if data_password == client_password:
                            client.sendall(pickle.dumps({'type': 'registration', 'message': 'ok'}))
                            self.clients_with_name[client] = client_name
                        else:
                            client.sendall(pickle.dumps({'type': 'registration', 'message': 'no'}))
                    else:
                        with self.lock:
                            self.names_passwords[client_name] = client_password
                            client.sendall(pickle.dumps({'type': 'registration', 'message': 'ok'}))
                            self.clients_with_name[client] = client_name

                if command == 'create_room':
                    room_name = message['room']
                    room = Room(room_name)
                    self.rooms.append(room)
                    room.add_client(client, client_name)
                    room.room_broadcast(msg_type='info', msg2_type='message', msg=f'{client_name} created {room_name}')

                if command == "join_room":
                    room_name = message['room']
                    for room in self.rooms:
                        if room.name == room_name:
                            room.add_client(client, client_name)
                            room.room_broadcast(msg_type='info', msg2_type='message',
                                                msg=f'{client_name} joined {room_name}')
                            break
                    else:
                        client.sendall(pickle.dumps({'type': 'info', 'message': "There's no room like this"}))

                elif command == "start_game":
                    room_name = message['room']
                    word = random.choice(self.dataset)

                    for room in self.rooms:
                        if room.name == room_name:
                            self.current_words[room_name] = word
                            room.room_broadcast(msg_type='start', msg2_type='word', msg=word)
                            break

                elif command == "submit_word":
                    room_name = message['room']
                    player = message['player']
                    word = message["word"]

                    for curr_room in self.rooms:
                        if room_name == curr_room.name:
                            room = curr_room

                            if (self.check_word(word=word, reference=self.current_words[room_name])
                                    and room.is_correct_word(word)):
                                self.scores[player] = self.scores.get(player, 0) + 1
                                room.room_broadcast(msg_type='score', msg2_type='scores', msg=self.scores)
                                room.words_history.append(word)
                                break

                elif command == 'exit':
                    self.clients.remove(client)
                    if room:
                        room.remove_client(client, client_name)

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


# Main Execution
if __name__ == "__main__":
    # Start server in a separate thread
    server = GameServer(HOST, PORT)
    threading.Thread(target=server.start).start()
