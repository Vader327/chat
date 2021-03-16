import sqlite3
import uuid

con = sqlite3.connect("database.db")
cur = con.cursor()

cur.execute("INSERT INTO users (id, name,password) VALUES (?,?,?)", (str(uuid.uuid4()), 'Vader27', 'test123'))
#cur.execute("ALTER TABLE rooms ADD COLUMN users TEXT")
#cur.execute("DELETE FROM users WHERE name = 'Chrome';")
con.commit()


"""
cur.execute(""
CREATE TABLE IF NOT EXISTS rooms (
    id TEXT NOT NULL,
    code TEXT NOT NULL,
    users TEXT NOT NULL
);
")
cur.execute("
CREATE TABLE IF NOT EXISTS users (
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    password TEXT NOT NULL
);            
")
"""
