# Jarvis
1.  Fill out your channel ID's and bot token in both jarvis.py and backfill.py
2.  pip install discord
3.  python backfill.py - first to get history of valid codes.  (Valid codes are only 1 word long between 5 and 30 alphanumeric characters long)
4.  python jarvis.py

   will generate a new list and start notifying of new valid codes as they come in.  Will remove codes from the list if their original message is deleted from the monitor channel.

UPDATE
 Now supports DB storage of info so please use new script to copy data into db and be sure to update db fields for proper function.

CREATE DATABASE IF NOT EXISTS cache_db;

USE cache_db;

CREATE TABLE word_list (
    id INT AUTO_INCREMENT PRIMARY KEY,
    message_id BIGINT NOT NULL,
    word VARCHAR(30) NOT NULL,
    user VARCHAR(255) NOT NULL,
    time DATETIME NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    removed_at DATETIME DEFAULT NULL,
    UNIQUE (word)
);
