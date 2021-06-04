import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify, request, redirect, url_for, render_template, session, abort
from flask_socketio import SocketIO, join_room, leave_room, send, emit, rooms
import os
import uuid
import sqlite3

app = Flask(__name__)
#app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SECRET_KEY'] = 'jgr8e8943t894hg954f9846fh456'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
#socketio = SocketIO(app, cors_allowed_origins='*')
#socketio = SocketIO(app)


"""
# To block the service that prevents the heroku dyno from sleeping,
# which polls the server every 5 minutes -
ip_ban_list = ['']
@app.before_request
def block_method():
  ip = request.environ.get('REMOTE_ADDR')
  if ip in ip_ban_list:
      abort(403)
"""


@app.route('/')
def index():
  username = session.get('username')
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
      all_rooms = cur.execute("SELECT id, name FROM rooms WHERE users LIKE '%" + username + "%'").fetchall()
      data['rooms'] = all_rooms

    data['username'] = username
    data['password'] = password
    data['uid'] = uid
    data['logged_in'] = True
    
  else:
    return redirect(url_for('login', from_invite = (data['from_invite'] if data['from_invite'] else None), invite_code=data['invite_code']))
  
  return render_template("index.html", data=data)



@app.route('/signup')
def signup():
  args = request.args
  return render_template('signup.html', from_invite=args.get('from_invite'), invite_code=args.get('invite_code'))

@app.route('/login')
def login():
  args = request.args
  return render_template('login.html', from_invite=args.get('from_invite'), invite_code=args.get('invite_code'))



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

      all_rooms = []
      for i in cur.execute("SELECT * FROM rooms WHERE users LIKE '%" + username + "%'").fetchall():
        all_rooms.append({
          'id': i[0],
          'name': i[1],
          'participants': i[2],
        })

      if username not in users_in_room:
        users_in_room.append(username)
        cur.execute("UPDATE rooms SET users = ? WHERE id = ?", (','.join(users_in_room), room))
        con.commit()

    data = {'username': username, 'room': room, 'room_name': room_name, 'participants': users_in_room, 'all_rooms': all_rooms}
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






############
##  APIs  ##
############



@app.route('/api/signup', methods=['POST'])
def signup_api():
  name = request.form['username']
  password = request.form['password']

  if not name.strip():
    return jsonify({'status': 'no_name'})
  
  elif not password.strip():
    return jsonify({'status': 'no_password'})

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
  


@app.route('/api/login', methods=['POST'])
def login_api():
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



@app.route('/api/signout', methods=['POST'])
def signout():
  session.clear()
  return redirect(url_for('index'))






###############
##  SOCKETS  ##
###############



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



@socketio.on('send_message', namespace='/chat')
def send_message(json):
  emit('receive_message', json, namespace='/chat', room=session.get('room'))

@socketio.on('typing_status', namespace='/chat')
def send_status(json):
  emit('status', {'username': session.get('username'), 'type': 'typing', 'typing': json['typing']}, namespace='/chat', room=session.get('room'))



if __name__ == "__main__":
  app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
  socketio.run(app, debug=True)
