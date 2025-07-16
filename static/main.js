/* static/main.js */
/* global io */

// 1️⃣  解析模板注入的数据
const cfg = JSON.parse(
  document.getElementById('init-data').textContent
);
const { room, boardSize } = cfg;

// 2️⃣  建立 Socket.IO 连接
// static/main.js 里 —— 找到 const socket = io(...) 那一行，替换成
const socket = io({
  transports: ['polling'],   // ← 只用轮询
  upgrade:    false          // ← 禁止升级 websocket
});


let playerIndex  = null;
let chosenPoison = false;

/* ---------- 事件 ---------- */
socket.on('connect', () => {
  socket.emit('join', { room, size: boardSize });
});

socket.on('joined', (d) => {
  playerIndex = d.playerIndex;
  document.getElementById('status').innerText =
    `你是玩家 #${playerIndex + 1}，请先点击任意食物设“毒药”。`;
});

socket.on('update', renderPool);
socket.on('error',   (d) => alert(d.msg));
socket.on('game_over', (d) => {
  alert(socket.id === d.winner ? '🎉 你赢了！' : '💀 你输了！');
  location.reload();
});

/* ---------- 渲染 ---------- */
function renderPool(game){
  const div = document.getElementById('foodPool');
  div.innerHTML = '';
  game.food.forEach((emoji, idx) => {
    const btn = document.createElement('button');
    btn.textContent = emoji;
    btn.onclick     = () => handleClick(idx);
    div.appendChild(btn);
  });
  document.getElementById('status').innerText =
    `房间玩家数：${game.total_players} ｜ ${
      game.turn_idx === playerIndex ? '轮到你' : '等待对手'
    }`;
}

/* ---------- 点击 ---------- */
function handleClick(idx){
  if(!chosenPoison){
    socket.emit('set_poison', { room, index: idx });
    chosenPoison = true;
    alert('毒药已设定，接下来正常走子');
    return;
  }
  socket.emit('eat', { room, index: idx });
}
