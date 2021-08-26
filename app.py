import sqlite3
import uuid
import os
from flask_socketio import SocketIO, join_room, leave_room, send, emit, rooms
from flask import (
    Flask,
    jsonify,
    request,
    redirect,
    url_for,
    render_template,
    session,
    abort,
)
import eventlet

eventlet.monkey_patch()


app = Flask(__name__)
# app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config["SECRET_KEY"] = "jgr8e8943t894hg954f9846fh456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
# socketio = SocketIO(app, cors_allowed_origins='*')
# socketio = SocketIO(app)


@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect(url_for("chat_index"))
    else:
        invite_code = request.args.get("invite_code")
        return redirect(
            url_for(
                "login",
                from_invite=(True if invite_code else None),
                invite_code=invite_code,
            )
        )


@app.route("/signup")
def signup():
    args = request.args
    return render_template(
        "signup.html",
        from_invite=args.get("from_invite"),
        invite_code=args.get("invite_code"),
    )


@app.route("/login")
def login():
    args = request.args
    return render_template(
        "login.html",
        from_invite=args.get("from_invite"),
        invite_code=args.get("invite_code"),
    )


@app.route("/room", methods=["GET", "POST"])
def room():
    from_invite = request.args.get("from_invite")

    if from_invite == "True":
        room = request.args.get("code")
        type_ = "join"

    else:
        room = request.form["room"]
        type_ = request.args.get("type")

    if type_ == "join":
        with sqlite3.connect("database.db") as con:
            cur = con.cursor()
            data = cur.execute("SELECT * FROM rooms WHERE id = ?", (room,)).fetchone()

            if data:
                session["room"] = room
                session["room_name"] = data[1]
                return jsonify({"status": "success"})

            else:
                return jsonify({"status": "room_doesnt_exist"})

    elif type_ == "create":
        room_id = str(uuid.uuid4()).split("-")[0]

        session["room"] = room_id
        session["room_name"] = room

        with sqlite3.connect("database.db") as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO rooms (id,name,users) VALUES (?,?,?)",
                (room_id, room, session["username"]),
            )
            con.commit()

        return jsonify({"status": "success", "room": room_id})


@app.route("/chat")
def chat_index():
    if session.get("logged_in"):
        with sqlite3.connect("database.db") as con:
            cur = con.cursor()
            data = cur.execute(
                "SELECT id FROM rooms WHERE users LIKE '%"
                + session.get("username")
                + "%'"
            ).fetchone()
            if data:
                room_id = data[0]
                return redirect(url_for("chat", room=room_id))
            else:
                return render_template(
                    "chat.html",
                    data={
                        "username": session.get("username"),
                    },
                )
    else:
        return redirect(url_for("index"))


@app.route("/chat/<room>", methods=["GET", "POST"])
def chat(room):
    username = session.get("username")
    session["room"] = room

    if session.get("logged_in"):
        with sqlite3.connect("database.db") as con:
            cur = con.cursor()
            data = cur.execute("SELECT * FROM rooms WHERE id = ?", (room,)).fetchone()
            room_name = data[1]
            users_in_room = data[2].split(",")

            if username not in users_in_room:
                users_in_room.append(username)
                cur.execute(
                    "UPDATE rooms SET users = ? WHERE id = ?",
                    (",".join(users_in_room), room),
                )
                con.commit()

            all_rooms = []
            for i in cur.execute(
                "SELECT * FROM rooms WHERE users LIKE '%" + username + "%'"
            ).fetchall():
                all_rooms.append(
                    {
                        "id": i[0],
                        "name": i[1],
                        "participants": i[2],
                    }
                )

        data = {
            "username": username,
            "room": room,
            "room_name": room_name,
            "participants": users_in_room,
            "all_rooms": all_rooms,
        }
        return render_template("chat.html", data=data)

    else:
        return redirect(url_for("index"))


@app.route("/invite")
def invite():
    logged_in = session.get("logged_in")
    code = request.args.get("code")
    session["room"] = code

    if logged_in:
        return render_template("invite.html", code=code)

    else:
        return redirect(url_for("index", invite_code=code))


############
##  APIs  ##
############


@app.route("/api/signup", methods=["POST"])
def signup_api():
    name = request.form["username"]
    password = request.form["password"]

    if not name.strip():
        return jsonify({"status": "no_name"})

    elif not password.strip():
        return jsonify({"status": "no_password"})

    with sqlite3.connect("database.db") as con:
        cur = con.cursor()
        data = cur.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()

        if data and data[1].strip().lower() == name.strip().lower():
            return jsonify({"status": "account_already_exists"})

        else:
            session["username"] = name
            session["logged_in"] = True

            user_id = str(uuid.uuid4()).split("-")
            user_id = "".join(user_id)

            with sqlite3.connect("database.db") as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO users (id,name,password) VALUES (?,?,?)",
                    (user_id, name, password),
                )
                con.commit()

            return jsonify({"status": "success"})


@app.route("/api/login", methods=["POST"])
def login_api():
    name = request.form["username"]
    password = request.form["password"]

    with sqlite3.connect("database.db") as con:
        cur = con.cursor()
        data = cur.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()

        if data:
            if data[2].strip().lower() == password.strip().lower():
                session["username"] = name
                session["logged_in"] = True

                return jsonify({"status": "success"})

            elif data[2].strip().lower() != password.strip().lower():
                return jsonify({"status": "incorrect_password"})

        else:
            return jsonify({"status": "account_doesnt_exists"})


@app.route("/api/leave", methods=["POST"])
def leave():
    room = session["room"]

    with sqlite3.connect("database.db") as con:
        cur = con.cursor()
        data = cur.execute("SELECT * FROM rooms WHERE id = ?", (room,)).fetchone()
        room_name = data[1]
        users_in_room = data[2].split(",")
        users_in_room.remove(session.get("username"))

        if not users_in_room:
            cur.execute(
                "DELETE FROM rooms WHERE id = ?",
                (room,),
            )
        
        else:
            cur.execute(
                "UPDATE rooms SET users = ? WHERE id = ?",
                (",".join(users_in_room), room),
            )
        con.commit()

    return redirect(url_for("chat_index"))


@app.route("/api/signout", methods=["POST"])
def signout():
    session.clear()
    return redirect(url_for("index"))


###############
##  SOCKETS  ##
###############


@socketio.on("join", namespace="/chat")
def join(json=None):
    if json:
        room = json["id"]
        session["room"] = room
        with sqlite3.connect("database.db") as con:
            cur = con.cursor()
            data = cur.execute(
                "SELECT name FROM rooms WHERE id = ?", (room,)
            ).fetchone()
            session["room_name"] = data[0]

    client_room = session.get("room")
    join_room(client_room, namespace="/chat")

    if not json:
        emit(
            "status",
            {"username": session.get("username"), "type": "join"},
            namespace="/chat",
            room=client_room,
        )


@socketio.on("leave", namespace="/chat")
def leave_message():
    client_room = session.get("room")
    leave_room(client_room, namespace="/chat")
    emit(
        "status",
        {"username": session.get("username"), "type": "leave"},
        namespace="/chat",
        room=client_room,
    )


@socketio.on("send_message", namespace="/chat")
def send_message(json):
    emit("receive_message", json, namespace="/chat", room=session.get("room"))


@socketio.on("typing_status", namespace="/chat")
def send_status(json):
    emit(
        "status",
        {
            "username": session.get("username"),
            "type": "typing",
            "typing": json["typing"],
        },
        namespace="/chat",
        room=session.get("room"),
    )


@socketio.on("change_room", namespace="/chat")
def change_room(json):
    emit(
        "status",
        {
            "username": session.get("username"),
            "type": "typing",
            "typing": json["typing"],
        },
        namespace="/chat",
        room=session.get("room"),
    )


if __name__ == "__main__":
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    socketio.run(app, debug=True)
    # socketio.run(app, debug=True, host="0.0.0.0")
