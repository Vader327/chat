from flask import Flask, jsonify, request, redirect, url_for, render_template, session
from flask_socketio import SocketIO, join_room, leave_room, send, emit, rooms
import os
import uuid
import sqlite3

app = Flask(__name__)
#app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SECRET_KEY'] = 'jgr8e8943t894hg954f9846fh456'
#socketio = SocketIO(app, cors_allowed_origins='*')
socketio = SocketIO(app)



@app.route('/')
def index():
  name = session.get('username')
  password = session.get('password')

  data={'username': None, 'password': None, 'logged_in': False}

  if name and password:
    #with sqlite3.connect("database.db") as con:
    #  cur = con.cursor()
    #  db_data = cur.execute("SELECT * FROM users WHERE name = ?", (name, )).fetchall()

    data['username'] = name
    data['password'] = password
    data['logged_in'] = True
  
  return render_template("index.html", data=data)



@app.route('/room', methods=['POST'])
def room():
  room = request.form['room']
  type_ = request.args.get('type')

  if type_ == "join":
    with sqlite3.connect("database.db") as con:
      cur = con.cursor()
      data = cur.execute("SELECT * FROM rooms WHERE id = ?", (room,)).fetchone()
      print("\n")
      print(data)
      print("\n")

      if data:
        session['room'] = room
        session['room_name'] = data[1]
        return jsonify({'status': 'success'})

      else:
        return jsonify({'status': 'room_doesnt_exist'})
  
  elif type_ == "create":
    room_id = str(uuid.uuid4()).split("-")[0]

    session['room'] = room_id
    session['room_name'] = room

    with sqlite3.connect("database.db") as con:
      cur = con.cursor()
      cur.execute("INSERT INTO rooms (id,name,users) VALUES (?,?,?)", (room_id, room, session['username'] + ','))
      con.commit()

    return jsonify({'status': 'success'})



@app.route('/signup', methods=['POST'])
def signup():
  name = request.form['username']
  password = request.form['password']

  with sqlite3.connect("database.db") as con:
    cur = con.cursor()
    data = cur.execute("SELECT * FROM users WHERE name = ?", (name, )).fetchone()

    if data and data[1].strip().lower() == name.strip().lower():
      return jsonify({'status': 'account_already_exists'})

    else:
      session['username'] = name
      session['password'] = password
      
      with sqlite3.connect("database.db") as con:
        cur = con.cursor()
        cur.execute("INSERT INTO users (id, name,password) VALUES (?,?,?)", (str(uuid.uuid4()), name, password))
        con.commit()

      return jsonify({'status': 'success'})
  


@app.route('/login', methods=['POST'])
def login():
  name = request.form['username']
  password = request.form['password']

  with sqlite3.connect("database.db") as con:
    cur = con.cursor()
    data = cur.execute("SELECT * FROM users WHERE name = ?", (name, )).fetchone()

    if data:
      if data[2].strip().lower() == password.strip().lower():
        session['username'] = name
        session['password'] = password
        return jsonify({'status': 'success'})
    
      elif data[2].strip().lower() != password.strip().lower():
        return jsonify({'status': 'incorrect_password'})
    
    else:
      return jsonify({'status': 'account_doesnt_exists'})



@app.route('/signout', methods=['POST'])
def signout():
  session['username'] = None
  session['password'] = None
  session['logged_in'] = False

  return redirect(url_for('index'))



@app.route('/chat', methods=['GET', 'POST'])
def chat():
  username = session.get('username')
  room = session.get('room')
  room_name = session.get('room_name')

  with sqlite3.connect("database.db") as con:
    cur = con.cursor()
    data = cur.execute("SELECT users FROM rooms WHERE id = ?", (room, )).fetchone()
    print(data)

  if username and room:
    data = {'username': username, 'room': room, 'room_name': room_name}
    return render_template("chat.html", data=data)
  else:
    return redirect(url_for('index'))



@socketio.on('join', namespace='/chat')
def join():
  client_room = session.get('room')
  join_room(client_room, namespace='/chat')
  print(rooms(request.sid))
  emit('status', {'username': session.get('username'), 'type': 'join'}, namespace='/chat', room=client_room)
  


@socketio.on('leave', namespace='/chat')
def leave():
  client_room = session.get('room')
  leave_room(client_room, namespace='/chat')
  emit('status', {'username': session.get('username'), 'type': 'leave'}, namespace='/chat', room=client_room)



@socketio.on('send message', namespace='/chat')
def send_message(json):
  print(rooms(request.sid))
  emit('receive message', json, namespace='/chat', room=session.get('room'))

"""
README

When person joins, print(rooms(request.sid)) prints an array of
the socket id and the room name

For example, if person from Room1 sends a message, the output is:
['435v463vg6vfgv645675v7h8', 'Room1']

And if person from Room2 sends a message, the output is:
['t9r8h9gf7h58u56y54rey859', 'Room2']

Store room in database so that they do not expire




Person joins room
  -  if room does not exist, it gets created in database

Person gets added in database
Messages are NOT stored in database, only transferred via sockets
If person leaves room, person gets removed from database
Participant list is retrieved from database
Only App users and rooms are stored in server, rooms containg the participants in it.
If user deletes account, remove user from room AND user list in database
"""





""" 
@socketio.on('fetch_participants', namespace='/chat')
def fetch_participants(methods=['GET', 'POST']):
  socketio.emit('return_participants', namespace='/chat')

con = sqlite3.connect("database.db")
cursor = con.cursor()
cursor.execute("CREATE TABLE active_rooms (id INTEGER PRIMARY KEY, room_name TEXT, participants TEXT)")
"""
  
if __name__ == "__main__":
  socketio.run(app, debug=True)
