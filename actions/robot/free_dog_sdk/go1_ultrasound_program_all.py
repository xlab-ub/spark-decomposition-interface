import socket
import threading

PORT = 12345
BUFFER_SIZE = 1024

def handle_client(client_socket, client_address):
    print(f"Connection established with {client_address}")

    while True:
        data = client_socket.recv(BUFFER_SIZE).decode('utf-8')
        if not data:
            print(f"Connection with {client_address} closed.")
            break  # Break the loop if no data received

        # Process the received data
        parts = data.split()
        if len(parts) == 1:
            data1 = float(parts[0])
            print(f"Received one double value from {client_address}: {data1}")
        elif len(parts) == 2:
            data1, data2 = float(parts[0]), float(parts[1]) # Ignore the labels
            print(f"Received two double values from {client_address}: left {data1}, right {data2}")
        else:
            print(f"Invalid data format received from {client_address}")

    # Close the client socket
    client_socket.close()

# Create a socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to a specific address and port
server_socket.bind(('0.0.0.0', PORT))

# Listen for incoming connections
server_socket.listen(5)
print(f"Listening for connections on port {PORT}...")

while True:
    # Accept a connection from a client
    client_socket, client_address = server_socket.accept()

    # Create a new thread to handle the client
    client_handler = threading.Thread(target=handle_client, args=(client_socket, client_address))
    client_handler.start()
