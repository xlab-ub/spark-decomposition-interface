import socket

PORT = 12345
BUFFER_SIZE = 1024

# Create a socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to a specific address and port
server_socket.bind(('0.0.0.0', PORT))

# Listen for incoming connections
server_socket.listen(5)
print(f"Listening for connections on port {PORT}...")

# Accept a connection from a client
client_socket, client_address = server_socket.accept()
print(f"Connection established with {client_address}")

# Receive data in a loop
while True:
    data = client_socket.recv(BUFFER_SIZE).decode('utf-8')
    if not data:
        break  # Break the loop if no data received

    # Convert string back to double
    double_value = float(data)
    print(f"Received double value: {double_value}")

# Close the sockets
client_socket.close()
server_socket.close()
