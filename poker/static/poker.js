const socket = io();
let lastState = null;
let myHole = [];
const chatsendid = "send_pgame_msg";
const chatreceiveid = "receive_pgame_msg";


socket.on("connect", () => {
    socket.emit("poker_join", { code: roomCode, username });
    socket.emit("set_page", { page: `Gaming:${roomCode}` });
});

socket.on("state", (data) => {
    lastState = data;
    render(data);
});

socket.on("hole_cards", (data) => {
    myHole = data.cards || [];
    renderHole();
});

socket.on("poker_error", (data) => {
    showNotif(data.msg, 3500);
});


function doBuyIn() {
    const amt = parseInt(document.getElementById("buy-in-input").value);
    socket.emit("poker_buy_in", { code: roomCode, username, amount: amt });
}

function startGame() {
    socket.emit("poker_start", { code: roomCode, username });
}

function doAction(action) {
    let amount = 0;
    if (action === "raise") {
        amount = parseInt(document.getElementById("raise-slider").value) || 0;
    }
    socket.emit("poker_action", { code: roomCode, username, action, amount });
    document.getElementById("action-bar").style.display = "none";
}

function nextHand() {
    socket.emit("poker_next_hand", { code: roomCode, username });
}

function leaveTable() {
    socket.emit("poker_leave", { code: roomCode, username });
    window.location.href = "/poker";
}

function copyCode() {
    navigator.clipboard.writeText(roomCode);
    showNotif("Room code copied!");
}


const CARD_SUITS = { S: "♠", H: "♥", D: "♦", C: "♣" };
const SUIT_COLOR = { S: "black", H: "red", D: "red", C: "black" };

function cardHTML(c, facedown = false) {
    if (facedown) {
        return `<div class="card-img"><img src="${previousCardBackURL}" draggable="false"></div>`;
    }
    const suit = c.slice(-1);
    const rank = c.slice(0, -1);
    const filename = rank + suit;
    return `
        <div class="card-img hole-card">
            <div class="card-face">
                <img src="/static/cards/${filename}.png" draggable="false">
            </div>
            <div class="card-back">
                <img src="${previousCardBackURL}" draggable="false">
            </div>
        </div>`;
}

const CHIPS = [
    { value: 1000, cls: 'chip-1k', label: '1K' },
    { value: 500, cls: 'chip-500', label: '500' },
    { value: 100, cls: 'chip-100', label: '100' },
    { value: 50, cls: 'chip-50', label: '50' },
    { value: 25, cls: 'chip-25', label: '25' },
    { value: 10, cls: 'chip-10', label: '10' },
    { value: 5, cls: 'chip-5', label: '5' },
    { value: 1, cls: 'chip-1', label: '1' },
];

function chipsHTML(amount) {
    if (!amount || amount <= 0) {
        return `<span class="chip-zero">-</span>`;
    }

    let remaining = amount;
    let denominations = [];

    for (const chip of CHIPS) {
        const count = Math.floor(remaining / chip.value);
        if (count > 0) {
            denominations.push({ ...chip, count: Math.min(count, 5) });
            remaining -= count * chip.value;
        }
        if (denominations.length >= 4) break;
    }

    let html = `<span class="chip-stack-wrap">`;
    for (const d of denominations) {
        const show = Math.min(d.count, 3);
        html += `<span style="display:inline-flex;align-items:center;position:relative">`;
        for (let i = 0; i < show; i++) {
            html += `<span class="chip ${d.cls}" style="margin-left:${i === 0 ? 0 : -10}px;z-index:${i}">${i === show - 1 ? d.label : ''}</span>`;
        }
        if (d.count > 3) {
            html += `<span style="font-size:9px;color:#ffd97a;margin-left:2px;font-family:'Cinzel',serif">×${d.count}</span>`;
        }
        html += `</span>`;
    }

    const display = amount >= 1000 ? (amount / 1000).toFixed(1).replace(/\.0$/, '') + 'k' : amount;
    html += `<span class="chips-amount">${display}</span></span>`;
    return html;
}

function renderHole() {
    const el = document.getElementById("your-hole");
    if (!el) return;
    el.innerHTML = myHole.map(c => cardHTML(c)).join("");
}

const OPP_POSITIONS = [
    ["pos-top"],
    ["pos-left", "pos-right"],
    ["pos-left", "pos-top", "pos-right"],
    ["pos-topleft", "pos-top", "pos-topright", "pos-right"],
];

function render(data) {
    const phase = data.phase || "lobby";

    document.getElementById("lobby-overlay").classList.toggle("open", phase === "lobby");
    document.getElementById("showdown-overlay").classList.toggle("open", phase === "showdown" || phase === "done");

    if (phase === "lobby") { renderLobby(data); return; }
    if (phase === "showdown" || phase === "done") { renderShowdown(data); }

    const board = data.board || [];
    document.getElementById("board-cards").innerHTML = board.map(c => cardHTML(c)).join("");
    document.getElementById("pot-label").innerHTML =
        data.pot > 0 ? `<span class="pot-wrap">POT ${chipsHTML(data.pot)}</span>` : "";
    document.getElementById("phase-label").textContent = phase.toUpperCase();

    const myStack = data.stacks?.[username] ?? 0;
    document.getElementById("stack-pill").innerHTML = chipsHTML(myStack);

    const players = data.players || [];
    const n = players.length;
    const dealerIdx = data.dealer ?? 0;
    const myIdx = players.indexOf(username);
    const amDealer = myIdx === dealerIdx % n;
    const amSB = myIdx === (dealerIdx + 1) % n;
    const amBB = myIdx === (dealerIdx + 2) % n;

    const myBadge = amDealer ? `<span class="pos-badge dealer">D</span>`
        : amSB ? `<span class="pos-badge sb">SB</span>`
            : amBB ? `<span class="pos-badge bb">BB</span>`
                : "";
    document.getElementById("your-name").innerHTML = `${myBadge} ${username}`;

    const myTurn = data.action_on === username;
    document.getElementById("turn-pill").classList.toggle("visible", myTurn);

    const actionBar = document.getElementById("action-bar");
    if (myTurn && phase !== "showdown") {
        actionBar.style.display = "flex";
        const maxBet = data.bets ? Math.max(...Object.values(data.bets), 0) : 0;
        const myBet = data.bets?.[username] || 0;
        const toCall = maxBet - myBet;
        const stack = data.stacks?.[username] || 0;
        const btnCheck = document.getElementById("btn-check");
        const btnCall = document.getElementById("btn-call");
        btnCheck.style.display = toCall === 0 ? "inline-block" : "none";
        btnCall.style.display = toCall > 0 ? "inline-block" : "none";
        btnCall.textContent = `Call ${toCall}`;
        const slider = document.getElementById("raise-slider");
        const minR = data.min_raise || 0;
        slider.min = minR;
        slider.max = stack;
        slider.value = Math.min(Math.max(slider.value, minR), stack);
        updateRaiseLabel();
    } else {
        actionBar.style.display = "none";
    }

    renderHole();

    const oppContainer = document.getElementById("opp-container");
    oppContainer.innerHTML = "";
    const opponents = (data.players || []).filter(p => p !== username);
    const slots = opponents.length >= 1 && opponents.length <= 4
        ? OPP_POSITIONS[opponents.length - 1]
        : opponents.map((_, i) => ["pos-top", "pos-left", "pos-right", "pos-topleft", "pos-topright"][i % 5]);

    opponents.forEach((p, idx) => {
        const pos = slots[idx] || "pos-top";
        const isActive = data.action_on === p;
        const folded = (data.folded || []).includes(p);
        const allIn = (data.all_in || []).includes(p);
        const stack = data.stacks?.[p] ?? 0;
        const bet = data.bets?.[p] ?? 0;

        const players = data.players || [];
        const n = players.length;
        const dealerIdx = data.dealer ?? 0;
        const pIdx = players.indexOf(p);
        const isDealer = pIdx === dealerIdx % n;
        const isSB = pIdx === (dealerIdx + 1) % n;
        const isBB = pIdx === (dealerIdx + 2) % n;

        const badge = isDealer ? `<span class="pos-badge dealer">D</span>`
            : isSB ? `<span class="pos-badge sb">SB</span>`
                : isBB ? `<span class="pos-badge bb">BB</span>`
                    : "";

        const zone = document.createElement("div");
        zone.className = `opp-zone ${pos}${isActive ? " active-zone" : ""}${folded ? " folded-zone" : ""}`;

        zone.innerHTML = `
            <div class="opp-name${isActive ? " their-turn" : ""}">${badge} ${p}${allIn ? " 🔴" : ""}</div>
            <div class="opp-cards-row">
                ${cardHTML("back", true)}${cardHTML("back", true)}
            </div>
            <div class="opp-meta">
                ${chipsHTML(stack)}${bet > 0 ? `<span class="bet-badge">bet ${bet}</span>` : ""}
                ${folded ? `<em class="fold-tag">folded</em>` : ""}
            </div>`;
        oppContainer.appendChild(zone);
    });
}

function updateRaiseLabel() {
    const v = document.getElementById("raise-slider").value;
    document.getElementById("raise-label").textContent = v;
}

function renderLobby(data) {
    const level = { low: { min: 200, max: 1000 }, mid: { min: 1000, max: 5000 }, high: { min: 5000, max: 25000 } };
    const lvl = level[data.stake] || level.low;
    document.getElementById("lobby-info").textContent =
        `${data.stake?.toUpperCase()} table · Blinds ${data.blinds || ""} · Buy-in ${lvl.min}–${lvl.max}`;
    document.getElementById("buy-in-input").min = lvl.min;
    document.getElementById("buy-in-input").max = Math.min(lvl.max, myChips);
    document.getElementById("buy-in-input").value = Math.min(lvl.min, myChips);

    const stacks = data.stacks || {};
    const hasBoughtIn = (stacks[username] || 0) > 0;
    document.getElementById("buy-in-section").style.display = hasBoughtIn ? "none" : "block";
    document.getElementById("buy-in-status").textContent = hasBoughtIn ? `Stack: ${stacks[username]}` : "";

    const playerList = document.getElementById("player-list");
    playerList.innerHTML = (data.players || []).map(p =>
        `<div class="plr-row">${p} ${stacks[p] > 0 ? `· ${stacks[p]} chips` : "· not bought in"}</div>`
    ).join("");

    const isHost = data.host === username;
    const startBtn = document.getElementById("start-btn");
    startBtn.style.display = isHost ? "block" : "none";
}

function renderShowdown(data) {
    const results = data.last_result || {};
    const board = data.board || [];
    document.getElementById("showdown-results").innerHTML = `
        <div class="board-show">${board.map(c => cardHTML(c)).join("")}</div>
        <table class="res-table">
            <tr><th>Player</th><th>Hand</th><th>Cards</th><th>Won</th></tr>
            ${Object.entries(results).map(([p, r]) => `
            <tr class="${r.won > 0 ? 'winner-row' : ''}">
                <td>${p}</td>
                <td>${r.folded ? "Folded" : r.hand || "-"}</td>
                <td>${(r.cards || []).map(c => cardHTML(c)).join("")}</td>
                <td>${r.won > 0 ? `+${r.won}` : ""}</td>
            </tr>`).join("")}
        </table>`;
    const isHost = data.host === username;
    document.getElementById("next-hand-btn").style.display = (isHost && data.phase === "showdown") ? "block" : "none";
}


function showNotif(msg, dur = 2500) {
    const el = document.getElementById("notif");
    el.textContent = msg; el.style.display = "block";
    clearTimeout(el._t);
    el._t = setTimeout(() => el.style.display = "none", dur);
}
