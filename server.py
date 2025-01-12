import json
import time
from collections import Counter
import pickle
import random
import socket
import threading
from threading import Lock
from data.words import Words
# Constants
HOST = '127.0.0.1'
PORT = 65432


class Room:
    def __init__(self, name: str, client: 'GameServer'):
        self.name = name
        self.client = client

        self.clients = []
        self.names = []  # type: [str]
        self.words_history = []  # type: [str]
        self.game_started = False
        self.active_players = []

        self.scores = Counter()
        self.current_word = ''
        self.current_winner = ()  # type: (str, int)

        words = Words()
        self.dataset = words.words

    @staticmethod
    def check_word(reference, word):
        word_counter = Counter(word)
        reference_counter = Counter(reference)

        for letter, count in word_counter.items():
            if count > reference_counter.get(letter, 0):
                return False

        return True

    def start_game(self, client: socket.socket):
        if self.game_started:
            self.active_players.append(client)
        else:
            self.game_started = True
            self.active_players.append(client)
            self.room_broadcast(msg_type='info', msg2_type='message', msg='press start to play game', all=True)
            timer = threading.Timer(10, self.start)
            timer.start()

    def start(self):
        if len(self.active_players) > 1:
            self.current_word = random.choice(self.dataset)
            self.room_broadcast(msg_type='start', msg2_type='word', msg=self.current_word, all=False)
            timer = threading.Timer(10, self.game_end)
            timer.start()
        else:
            self.room_broadcast(msg_type='info', msg2_type='message', msg='you can not play alone', all=False)
            self.active_players.clear()
            self.game_started = False

    def game_end(self):
        self.room_broadcast(msg_type='end', msg2_type='message', msg='game ended', all=False)
        self.current_winner = self.scores.most_common(1)
        self.client.update_table(self.current_winner[0][0])

        self.active_players = []
        self.game_started = False
        self.scores.clear()
        self.words_history.clear()

    def submit_word(self, player, word):
        if (self.check_word(word=word, reference=self.current_word)
                and self.is_correct_word(word)):
            self.scores[player] = self.scores.get(player, 0) + 1
            self.room_broadcast(msg_type='score', msg2_type='scores', msg=self.scores, all=False)
            self.words_history.append(word)

    def room_broadcast(self, msg_type: str, msg2_type: str, msg, all: bool):
        if all:
            for client in self.clients:
                try:
                    client.sendall(pickle.dumps({"type": msg_type, msg2_type: msg}))
                except Exception as e:
                    print(f'connection error {e}')
                    self.clients.remove(client)
                    self.active_players.remove(client)
                    client.close()
        else:
            for client in self.active_players:
                try:
                    client.sendall(pickle.dumps({"type": msg_type, msg2_type: msg}))
                except Exception as e:
                    print(f'connection error {e}')
                    self.clients.remove(client)
                    self.active_players.remove(client)
                    client.close()

    def is_correct_word(self, word: str):
        if word in self.words_history:
            return False
        return True

    def add_client(self, client: socket.socket, name: str):
        if client not in self.clients:
            self.clients.append(client)
            self.names.append(name)

    def remove_client(self, client: socket.socket, name: str):
        if client in self.clients:
            self.clients.remove(client)
            # self.active_players.remove(client)
            self.names.remove(name)
            self.room_broadcast(msg_type='info', msg2_type='message', msg=f'player {name} left game', all=True)


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
        self.rooms_names = []

        # data of words
        words = Words()
        self.dataset = words.words
        self.current_words = {}  # type: {str: str} # {room_name: current_word}

        # for tables or scores
        self.scores = {}  # type: {str: int} # {client_name: score}
        self.table = Counter()

        print(f"Server started on {self.host}:{self.port}")

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

                    with open('data/passwords.json', 'r') as file:
                        data = json.load(file)
                        data_password = data.get(client_name, '')

                    if data_password:
                        if data_password == client_password:
                            client.sendall(pickle.dumps({'type': 'registration', 'message': 'ok'}))
                            time.sleep(0.3)
                            self.clients_with_name[client] = client_name
                            self.send_table(client)
                        else:
                            client.sendall(pickle.dumps({'type': 'registration', 'message': 'no'}))
                    else:
                        with self.lock:
                            data[client_name] = client_password

                            with open('data/passwords.json', 'w') as file:
                                json.dump(data, file, indent=4)

                            client.sendall(pickle.dumps({'type': 'registration', 'message': 'ok'}))
                            time.sleep(0.3)
                            self.clients_with_name[client] = client_name
                            self.send_table(client)

                if command == 'create_room':
                    if room:
                        room.remove_client(client, client_name)

                    room_name = message['room']
                    if room_name not in self.rooms_names:
                        client.sendall(pickle.dumps({'type': 'created', 'message': room_name}))

                        room = Room(room_name, self)
                        self.rooms.append(room)
                        self.rooms_names.append(room_name)
                        room.add_client(client, client_name)
                        room.room_broadcast(msg_type='info', msg2_type='message',
                                            msg=f'{client_name} created {room_name}', all=True)

                        self.rooms_update()

                    else:
                        client.sendall(pickle.dumps({'type': 'info',
                                                     'message': f'this room already created. you can join it'}))

                if command == "join_room":
                    if room:
                        room.remove_client(client, client_name)

                    room_name = message['room']

                    for room in self.rooms:
                        if room.name == room_name:
                            client.sendall(pickle.dumps({'type': 'joined', 'message': room_name}))
                            room.add_client(client, client_name)
                            room.room_broadcast(msg_type='info', msg2_type='message',
                                                msg=f'{client_name} joined {room_name}', all=True)
                            break
                    else:
                        client.sendall(pickle.dumps({'type': 'info', 'message': "There's no room like this"}))

                elif command == 'leave_room':
                    room.remove_client(client, client_name)
                    room.room_broadcast(msg_type='info', msg2_type='message', msg=f'{client_name} leave room', all=True)

                elif command == "start_game":
                    self.scores = {}
                    room.room_broadcast(msg_type='score', msg2_type='scores', msg=self.scores, all=True)

                    room.start_game(client=client)
                    client.sendall(pickle.dumps({'type': 'info', 'message': 'you are in game'}))

                elif command == "submit_word":
                    player = message['player']
                    word = message["word"]

                    room.submit_word(player, word)

                elif command == 'exit':
                    self.clients.remove(client)
                    if room:
                        room.remove_client(client, client_name)

        except Exception as e:
            print(f"Error with client {address}: {e}")
        finally:
            print(f"Closing connection with {address}")
            client.close()

    def rooms_update(self):
        time.sleep(0.3)
        for client in self.clients:
            try:
                client.sendall(pickle.dumps({'type': 'rooms', 'message': self.rooms_names}))
            except Exception as e:
                print(f'error with {client} with exception {e}')
                self.clients.remove(client)

    def update_table(self, client_name: str):
        with self.lock:
            with open('data/scores.json', 'r') as file:
                data = json.load(file)
                data[client_name] = data.get(client_name, 0) + 1

            send_table = dict(sorted(data.items(), key=lambda item: item[1], reverse=True))

            for client in self.clients:

                try:
                    client.sendall(pickle.dumps({'type': 'table', 'message': send_table}))
                except Exception as e:
                    print(f'error with {client} with exception {e}')
                    self.clients.remove(client)

            with open('data/scores.json', 'w') as file:
                json.dump(send_table, file, indent=4)

    def send_table(self, client: socket.socket):
        with open('data/scores.json', 'r') as file:
            data = json.load(file)

        try:
            client.sendall(pickle.dumps({'type': 'table', 'message': data}))
        except Exception as e:
            print(f'error with {client} with exception {e}')
            self.clients.remove(client)

    def start(self):
        """Start the server and handle incoming connections."""
        try:
            while True:
                client, address = self.server_socket.accept()
                with self.lock:
                    self.clients.append(client)
                threading.Thread(target=self.handle_client, args=(client, address), daemon=True).start()
        except KeyboardInterrupt:
            print("Shutting down server.")
        finally:
            self.server_socket.close()


# Main Execution
if __name__ == "__main__":
    server = GameServer(HOST, PORT)
    threading.Thread(target=server.start).start()
