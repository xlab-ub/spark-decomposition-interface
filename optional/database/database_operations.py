import os 
import sqlite3
    
def connect_to_database():
    # robot_instruction.db is in the same directory as this file
    file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'robot_instructions.db')
    return sqlite3.connect(file_path)

def create_tables():
    conn = connect_to_database()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE);")
    # Create new_function_library table
    cursor.execute("CREATE TABLE IF NOT EXISTS new_function_library (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, instruction TEXT NOT NULL, program TEXT NOT NULL, UNIQUE(user_id, instruction), FOREIGN KEY(user_id) REFERENCES users(id));")

    conn.commit()
    conn.close()

def insert_user(username):
    conn = connect_to_database()
    cursor = conn.cursor()
    # Insert or replace the user record
    cursor.execute("INSERT OR IGNORE INTO users (username) VALUES (?);", (username,))
    # Retrieve the user_id
    cursor.execute("SELECT id FROM users WHERE username = ?;", (username,))
    user_id = cursor.fetchone()[0]  # Assuming the username is unique
    conn.commit()
    conn.close()
    return user_id

def insert_new_function_library(user_id, instruction, program):
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO new_function_library (user_id, instruction, program) VALUES (?, ?, ?);", (user_id, instruction, program))
    conn.commit()
    conn.close()

def load_database_data(function_library, new_instruction_program_pair, user_id):
    new_function_library = {}
    new_instruction_program_pairs = ''
    
    conn = connect_to_database()
    cursor = conn.cursor()

    # Fetch function library records and update function_library, new_function_library, and new_instruction_program_pairs
    cursor.execute("SELECT instruction, program FROM new_function_library WHERE user_id = ?;", (user_id,))
    new_function_library_records = cursor.fetchall()
    
    conn.close()

    # print(f"new_function_library_records: {new_function_library_records}")
    for instruction, program in new_function_library_records:
        function_library.append(instruction)
        new_function_library[instruction] = program.split('\n')
        # Update new_instruction_program_pairs
        new_instruction_program_pairs += '\n' + new_instruction_program_pair.format(instruction=instruction, program=program+'\n') 
    
    return new_function_library, new_instruction_program_pairs
