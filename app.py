import eventlet
# —— 一定最先打补丁 —— 
eventlet.monkey_patch()

import random
import time
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-me'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ---------------- 房间状态 ----------------
rooms = {}  # room_id -> dict

def new_pool(size):
    pool = list("🍎🍇🍉🍌🍓🍒🍑🥭🍍🥝🍅"
                "🍆🥑🥦🥕🌽🥔🍞🥐🥨🧀🥚🍗"
                "🥩🥓🍤🍣🍪🍩🍰🧁🍦🍫🍿🍺☕🥤")
    return pool[:size*size]

AVATARS = ["🐶","🐱","🐭","🐹","🦊","🐰","🐻","🐼","🐨","🐯","🦁","🐮","🐷","🐸","🐵"]

# ---------------- 路由 ----------------
@app.route("/")
def lobby():
    return render_template("lobby.html")

@app.route("/create")
def create():
    size = int(request.args.get("size", 3))
    while True:
        room = str(random.randint(100, 999))
        if room not in rooms:
            break
    rooms[room] = {
        'food': new_pool(size),
        'board_size': size,
        'players': [],
        'avatars': None,
        'turn_idx': 0,
        'poisons': {},
        'last_seen': time.time()
    }
    return redirect(url_for("game", room=room))

@app.route("/game")
def game():
    room = request.args.get("room", "")
    if room not in rooms:
        return redirect(url_for("lobby"))
    size = rooms[room]['board_size']
    return render_template("game.html", room=room, board_size=size)

# ---------------- Socket.IO 处理 ----------------
def view_state(g):
    return {
        'food': g['food'],
        'total_players': len(g['players']),
        'turn_idx': g['turn_idx'],
    }

@socketio.on("join")
def handle_join(data):
    room = data.get("room")
    sid  = request.sid
    if room not in rooms:
        emit("error", {'msg': '房间不存在'})
        return

    g = rooms[room]
    join_room(room)
    g['last_seen'] = time.time()

    if g['avatars'] is None:
        g['avatars'] = random.sample(AVATARS, 2)

    if sid not in g['players']:
        if len(g['players']) >= 2:
            emit("error", {'msg': '房间已满'})
            leave_room(room)
            return
        g['players'].append(sid)

    idx = g['players'].index(sid)
    emit("joined", {
        'playerIndex': idx,
        'myAvatar':    g['avatars'][idx],
        'oppAvatar':   g['avatars'][1-idx]
    }, to=sid)

    emit("update", view_state(g), room=room)

@socketio.on("set_poison")
def handle_set_poison(data):
    room = data.get("room")
    idx  = data.get("index")
    sid  = request.sid
    g = rooms.get(room)
    if not g or sid in g['poisons'] or not (0 <= idx < len(g['food'])):
        emit("error", {'msg': '非法操作'})
        return
    g['poisons'][sid] = idx
    emit("update", view_state(g), room=room)

@socketio.on("eat")
def handle_eat(data):
    room = data.get("room")
    idx  = data.get("index")
    sid  = request.sid
    g = rooms.get(room)
    if not g:
        emit("error", {'msg': '房间不存在'}); return
    if g['players'][g['turn_idx']] != sid or g['food'][idx] == "💋":
        emit("error", {'msg': '非法操作'}); return
    opp = next((p for p in g['players'] if p != sid), None)
    if opp is None:
        emit("error", {'msg': '等待对手'}); return

    if idx == g['poisons'].get(opp, -1):
        emit("game_over", {'winner': opp}, room=room)
        rooms.pop(room, None)
    else:
        me_idx = g['players'].index(sid)
        avatar = g['avatars'][me_idx]
        g['food'][idx] = avatar
        g['turn_idx'] ^= 1
        emit("update", view_state(g), room=room)

@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    for room, g in list(rooms.items()):
        if sid in g['players']:
            g['players'].remove(sid)
            g['poisons'].pop(sid, None)
            g['last_seen'] = time.time()
            if g['players']:
                g['turn_idx'] %= len(g['players'])
                emit("update", view_state(g), room=room)
            else:
                rooms.pop(room, None)
            break

# 后台清理线程
def janitor():
    while True:
        now = time.time()
        for r, g in list(rooms.items()):
            if not g['players'] and now - g['last_seen'] > 30:
                rooms.pop(r, None)
        eventlet.sleep(5)

eventlet.spawn(janitor)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)
