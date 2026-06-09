import socket
import threading

PORT = 12345
BUFFER_SIZE = 32

# EMA filter
class EMA:
    def __init__(self, alpha):
        self.alpha = alpha
        self.value = None

    def update(self, new_value):
        if self.value is None:
            self.value = new_value
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value

    def get(self):
        return self.value

class go1_ultrasound:
    def __init__(self, port, debug=False):
        self.port = port
        self.buffer_size = BUFFER_SIZE
        self.debug = debug

        self.lock = threading.Lock()
        self.condition = threading.Condition()
        self.sensor_face_data = EMA(0.8)  # EMA filter
        self.sensor_left_data = EMA(0.8)  # EMA filter
        self.sensor_right_data = EMA(0.8)  # EMA filter
        self.connected_sensors = 0

        self.measured_value_from_face_sensor = None
        self.measured_value_from_left_sensor = None
        self.measured_value_from_right_sensor = None

        # Create a socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Bind the socket to a specific address and port
        self.server_socket.bind(('0.0.0.0', PORT))
        # Listen for incoming connections
        self.server_socket.listen(5)
        if self.debug:
            print(f"Listening for connections on port {PORT}...")
        threading.Thread(target=self.connect).start()

    def handle_client(self, client_socket, client_address):
        if self.debug:
            print(f"Connection established with {client_address}")

        # with self.lock:
        #     self.connected_sensors += 1
        #     self.condition.notify_all()

        while True:
            data = client_socket.recv(BUFFER_SIZE).decode('utf-8')
            if not data:
                if self.debug:
                    print(f"Connection with {client_address} closed.")
                with self.condition: 
                    with self.lock:
                        self.connected_sensors -= 1
                        self.condition.notify_all()
                break
            # Process the received data
            parts = data.split()
            if len(parts) == 1:
                try:
                    data1 = float(parts[0])
                    self.sensor_face_data.update(data1)
                except ValueError:
                    data1 = self.sensor_face_data.get()
                    if self.debug:
                        print(f"Received invalid data from {client_address}: {parts}")
                self.measured_value_from_face_sensor = data1
                if self.debug:
                    print(f"Received one double value from {client_address}: {data1}")
            elif len(parts) == 2:
                try:
                    data1, data2 = float(parts[0]), float(parts[1])
                    self.sensor_left_data.update(data1)
                    self.sensor_right_data.update(data2)
                except ValueError:
                    data1, data2 = self.sensor_left_data.get(), self.sensor_right_data.get()
                    if self.debug:
                        print(f"Received invalid data from {client_address}: {parts}")
                self.measured_value_from_left_sensor = data1
                self.measured_value_from_right_sensor = data2
                if self.debug:
                    print(f"Received two double values from {client_address}: left {data1}, right {data2}")
            else:
                if self.debug:
                    print(f"Invalid data format received from {client_address}")
        # Close the client socket
        client_socket.close()

    def run(self):
        while True:
            with self.condition:
                if self.connected_sensors == 2:
                    yield self.measured_value_from_face_sensor, self.measured_value_from_left_sensor, self.measured_value_from_right_sensor

    def connect(self):
        while True:
            with self.condition:
                if self.connected_sensors < 2:
                    with self.lock:
                        self.connected_sensors += 1
                        self.condition.notify_all()
                    client_socket, client_address = self.server_socket.accept()
                    threading.Thread(target=self.handle_client, args=(client_socket, client_address)).start()


if __name__ == "__main__":
    ultrasound = go1_ultrasound(PORT, debug=True)
    try:
        ultrasound_data_generator = ultrasound.run()
        while True:
            face, left, right = next(ultrasound_data_generator)
            print(f"Face: {face}, Left: {left}, Right: {right}")
    except KeyboardInterrupt:
        pass
