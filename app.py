import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify, request, redirect, url_for, render_template, session
from flask_socketio import SocketIO, join_room, leave_room, send, emit, rooms
import os
import uuid
import sqlite3
#from eventlet import wsgi
#import eventlet

#eventlet.monkey_patch()

app = Flask(__name__)
#app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SECRET_KEY'] = 'jgr8e8943t894hg954f9846fh456'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
#socketio = SocketIO(app)



@app.route('/')
def index():
  name = session.get('username')
  password = session.get('password')
  uid = session.get('uid')
  invite_code = request.args.get('invite_code')

  data={'username': None, 'password': None, 'uid': None, 'logged_in': False, 'rooms': [], 'from_invite': False, 'invite_code': None}

  if invite_code:
    data['from_invite'] = True
    data['invite_code'] = invite_code

  if session.get('logged_in'):
    with sqlite3.connect("database.db") as con:
      cur = con.cursor()
      all_rooms = cur.execute("SELECT id, name FROM rooms WHERE users LIKE '%" + name + "%'").fetchall()
      data['rooms'] = all_rooms

    data['username'] = name
    data['password'] = password
    data['uid'] = uid
    data['logged_in'] = True
  
  return render_template("index.html", data=data)



@app.route('/room', methods=['GET','POST'])
def room():
  from_invite = request.args.get('from_invite')

  if from_invite == 'True':
    room = request.args.get('code')
    type_ = "join"
  
  
  else:
    room = request.form['room']
    type_ = request.args.get('type')


  if type_ == "join":
    with sqlite3.connect("database.db") as con:
      cur = con.cursor()
      data = cur.execute("SELECT * FROM rooms WHERE id = ?", (room,)).fetchone()

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
      session['logged_in'] = True

      user_id = str(uuid.uuid4()).split("-")
      user_id = "".join(user_id)
      
      with sqlite3.connect("database.db") as con:
        cur = con.cursor()
        cur.execute("INSERT INTO users (id, name,password) VALUES (?,?,?)", (user_id, name, password))
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
        session['logged_in'] = True
        session['uid'] = data[0]

        return jsonify({'status': 'success'})
    
      elif data[2].strip().lower() != password.strip().lower():
        return jsonify({'status': 'incorrect_password'})
    
    else:
      return jsonify({'status': 'account_doesnt_exists'})



@app.route('/signout', methods=['POST'])
def signout():
  session.clear()
  return redirect(url_for('index'))



@app.route('/chat', methods=['GET', 'POST'])
def chat():
  username = session.get('username')
  room = session.get('room')
  room_name = session.get('room_name')

  if session.get('logged_in') and room:    
    with sqlite3.connect("database.db") as con:
      cur = con.cursor()
      data = cur.execute("SELECT users FROM rooms WHERE id = ?", (room, )).fetchone()

      users_in_room = data[0].split(",")

      if username not in users_in_room:
        users_in_room.append(username)

        cur.execute("UPDATE rooms SET users = ? WHERE id = ?", (','.join(users_in_room), room))
        con.commit()

    data = {'username': username, 'room': room, 'room_name': room_name, 'participants': users_in_room}
    return render_template("chat.html", data=data)

  else:
    return redirect(url_for('index'))

@app.route('/invite')
def invite():
  logged_in = session.get('logged_in')
  code = request.args.get('code')
  session['room'] = code

  if logged_in:
    return render_template('invite.html', code=code)

  else:
    return redirect(url_for('index', invite_code=code))



@socketio.on('join', namespace='/chat')
def join():
  client_room = session.get('room')
  join_room(client_room, namespace='/chat')

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

@socketio.on('typing_status', namespace='/chat')
def send_status(json):
  emit('status', {'username': session.get('username'), 'type': 'typing', 'typing': json['typing']}, namespace='/chat', room=session.get('room'))

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
  #wsgi.server(eventlet.listen(('', 5000)), app)
  #socketio.run(app, logger=True, engineio_logger=True)
  socketio.run(app)
  