import json
import mysql.connector

def migrate_json_to_db(json_file_path):
    # Load data from the existing JSON cache file
    with open(json_file_path, 'r') as file:
        data = json.load(file)

    # Connect to the MariaDB database
    conn = mysql.connector.connect(
        host="localhost",
        user="user",
        password="pass",
        database="cache_db",
        port=3306,
        charset='utf8mb4',  # Ensure the correct charset
        collation='utf8mb4_unicode_ci'  # Use a compatible collation
    )
    cursor = conn.cursor()

    # Insert each word entry from the JSON into the database
    for message_id, entry in data.items():
        cursor.execute("""
            INSERT INTO word_list (message_id, word, user, time)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE word = VALUES(word), user = VALUES(user), time = VALUES(time)
        """, (message_id, entry["word"], entry["user"], entry["time"]))

    conn.commit()
    cursor.close()
    conn.close()
    print("Migration completed.")

# Migrate data from the JSON file to the database
migrate_json_to_db('word_list_cache.json')
