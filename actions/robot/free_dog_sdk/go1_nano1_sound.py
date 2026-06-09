import paramiko
import os

class Nano1Connection:
    def __init__(self, nano1_ip, private_key_path, remote_directory, username="unitree"):
        self.nano1_ip = nano1_ip
        self.private_key_path = os.path.expanduser(private_key_path)
        self.remote_directory = remote_directory
        self.username = username
        self.ssh = None
        self.scp = None
        self.connect()

    def connect(self):
        try:
            # Create an SSH client with key-based authentication
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Load the private key
            private_key = paramiko.RSAKey(filename=self.private_key_path)

            # Connect to Nano 1 with key-based authentication
            self.ssh.connect(self.nano1_ip, username=self.username, pkey=private_key)

            # Create an SCP client
            self.scp = self.ssh.open_sftp()

        except paramiko.SSHException as e:
            print(f"SSH Error: {e}")
            raise(e)
        except Exception as e:
            print(f"Error: {e}")
            raise(e)

    def transfer_and_play_wav(self, wav_file_path, remote_filename=None):
        try:
            # Transfer the WAV file to Nano 1
            if remote_filename is None:
                remote_filename = 'speech.wav'
            
            remote_file_path = os.path.join(self.remote_directory, remote_filename)
            self.scp.put(wav_file_path, remote_file_path)

            # Execute the command to play the WAV file on Nano 1
            command = f'aplay -D plughw:2,0 {remote_file_path}'
            # command = f'aplay -D plughw:2,0 {os.path.join(self.remote_directory, remote_filename)}'
            stdin, stdout, stderr = self.ssh.exec_command(command)

            # Print the command output
            print(stdout.read().decode('utf-8'))

        except Exception as e:
            print(f"Error: {e}")
            raise(e)

    def close(self):
        # Close the SSH connection
        if self.ssh:
            self.ssh.close()
        if self.scp:
            self.scp.close()

if __name__ == '__main__':
    # Example usage
    try:
        # Create and initialize the connection
        nano1_connection = Nano1Connection('192.168.123.13', '~/.ssh/id_rsa', '/home/unitree/audio/files') 

        # Transfer and play the WAV file
        current_dir = os.path.dirname(os.path.realpath(__file__))
        filename = 'speech.wav'
        nano1_connection.transfer_and_play_wav(os.path.join(current_dir, filename), filename)
        # nano1_connection.transfer_and_play_wav('speech.wav')
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Close the connection when done
        if nano1_connection:
            nano1_connection.close()
