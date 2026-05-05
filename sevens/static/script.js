const socket = io();
let lastState = null;

const RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];
const SUITS = ["H", "D", "C", "S"];
const SUIT_SYM = { H: "♥", D: "♦", C: "♣", S: "♠" };
const RED_SUITS = ["H", "D"];
const CARD_H = 76;
const OVERLAP = 18;

const OPP_SLOTS = [
    ["pos-top"],
    ["pos-left", "pos-right"],
    ["pos-left", "pos-top", "pos-right"],
    ["pos-topleft", "pos-top", "pos-topright", "pos-right"],
    ["pos-left", "pos-topleft", "pos-top", "pos-topright", "pos-right"],
];

function getRank(c) { return c.slice(0, -1); }
function getSuit(c) { return c.slice(-1); }
function rankVal(c) { return RANKS.indexOf(getRank(c)); }
function cardImg(c) { return `url('/static/cards/${c}.png')`; }

function canPlay(board, card) {
    const r = getRank(card);
    const s = getSuit(card);
    const rv = RANKS.indexOf(r);
    if (r === "7") return true;
    const ss = board[s];
    if (!ss) return false;
    return rv === ss.low - 1 || rv === ss.high + 1;
}

function getPlayable(board, hand) {
    return hand.filter(c => canPlay(board, c));
}

function showNotif(msg, dur = 2500) {
    const el = document.getElementById("notif");
    el.textContent = msg; el.style.display = "block";
    clearTimeout(el._t); el._t = setTimeout(() => el.style.display = "none", dur);
}

function showFeedToast(html) {
    const feed = document.getElementById("play-feed");
    const el = document.createElement("div");
    el.className = "feed-toast";
    el.innerHTML = html;
    feed.appendChild(el);
    while (feed.children.length > 4) feed.removeChild(feed.firstChild);
    setTimeout(() => {
        el.classList.add("bye");
        setTimeout(() => el.remove(), 380);
    }, 3800);
}

function suitHtml(s) {
    const sym = SUIT_SYM[s];
    return RED_SUITS.includes(s) ? `<span class="red-txt">${sym}</span>` : sym;
}

function detectPlays(newState) {
    if (!lastState) return;
    const actor = lastState.turn;
    if (!actor) return;
    const oldBoard = lastState.board || {};
    const newBoard = newState.board || {};
    const newCompleted = newState.completed || [];
    const oldCompleted = lastState.completed || [];
    const who = actor === username ? "<span class='fp'>You</span>" : `<span class='fp'>${actor}</span>`;

    for (const s of SUITS) {
        const oldS = oldBoard[s];
        const newS = newBoard[s];
        if (!newS) continue;
        if (!oldS) {
            showFeedToast(`${who} played <b>7${suitHtml(s)}</b>`);
            if (newCompleted.includes(s)) showFeedToast(`${who} completed ${suitHtml(s)} — extra turn!`);
            return;
        }
        if (newS.low < oldS.low) {
            showFeedToast(`${who} played <b>${RANKS[newS.low]}${suitHtml(s)}</b>`);
            if (!oldCompleted.includes(s) && newCompleted.includes(s)) showFeedToast(`${who} completed ${suitHtml(s)} — extra turn!`);
            return;
        }
        if (newS.high > oldS.high) {
            showFeedToast(`${who} played <b>${RANKS[newS.high]}${suitHtml(s)}</b>`);
            if (!oldCompleted.includes(s) && newCompleted.includes(s)) showFeedToast(`${who} completed ${suitHtml(s)} — extra turn!`);
            return;
        }
    }
    if (newState.turn !== lastState.turn) showFeedToast(`${who} passed`);
}
socket.on("connect", () => socket.emit("sevens_join", { code: roomCode, username }));
socket.on("sevens_state", (data) => { detectPlays(data); lastState = data; render(data); });
socket.on("sevens_invalid", (data) => showNotif(data.msg || "Invalid move!"));

function startGame() { socket.emit("sevens_start", { code: roomCode }); }
function playCard(card) { socket.emit("sevens_play", { code: roomCode, username, card }); }
function passGo() { socket.emit("sevens_pass", { code: roomCode, username }); }

function makeVertStack(cards) {
    const VERT_OVERLAP = 22;
    const wrap = document.createElement("div");
    wrap.className = "card-stack";
    wrap.style.height = (CARD_H + Math.max(0, cards.length - 1) * VERT_OVERLAP) + "px";
    wrap.style.width = "var(--card-w)";
    wrap.style.position = "relative";
    console.log(cards)
    cards.forEach((card, i) => {
        const d = document.createElement("div");
        d.className = "stack-card";
        d.style.backgroundImage = cardImg(card);
        d.style.top = (i * VERT_OVERLAP) + "px";
        d.style.zIndex = i;
        if (getRank(card) === "7") {
            d.style.border = "2px solid var(--gold)";
            d.style.boxShadow = "0 0 10px rgba(212,168,67,0.5)";
        }
        wrap.appendChild(d);
    });
    return wrap;
}

function render(data) {
    const phase = data.phase || "lobby";
    const myTurn = data.turn === username;
    const hand = data.hands?.[username] || [];
    const board = data.board || {};
    const completed = data.completed || [];
    const playable = getPlayable(board, hand);

    for (const s of SUITS) {
        const ss = board[s];
        const isComplete = completed.includes(s);
        const rowEl = document.getElementById(`row-${s}`);

        Array.from(rowEl.children).forEach(ch => {
            if (!ch.classList.contains("suit-label")) ch.remove();
        });

        if (isComplete) {
            const slot = document.createElement("div");
            slot.className = "suit-stack completed-col";
            const stack = makeVertStack(["A" + s]);
            slot.appendChild(stack);
            const badge = document.createElement("div");
            badge.className = "complete-badge";
            badge.textContent = "✓ Complete";
            slot.appendChild(badge);
            rowEl.appendChild(slot);

        } else if (ss) {
            const col = document.createElement("div");
            col.className = "suit-stack";
            col.style.display = "flex";
            col.style.flexDirection = "column";
            col.style.alignItems = "center";
            const cards = [];
            for (let i = ss.low; i <= ss.high; i++) cards.push(RANKS[i] + s);
            cards.reverse();
            col.appendChild(makeVertStack(cards));
            rowEl.appendChild(col);
        } else {
            const placeholder = document.createElement("div");
            placeholder.className = "seven-placeholder";
            placeholder.textContent = "7" + SUIT_SYM[s];
            rowEl.appendChild(placeholder);
        }
    }

    const oppContainer = document.getElementById("opp-container");
    oppContainer.innerHTML = "";
    const opponents = Object.keys(data.hands || {}).filter(p => p !== username);
    const slots = opponents.length >= 1 && opponents.length <= 5
        ? OPP_SLOTS[opponents.length - 1]
        : opponents.map((_, i) => ["pos-top", "pos-left", "pos-right", "pos-topleft", "pos-topright"][i % 5]);

    opponents.forEach((p, idx) => {
        const pos = slots[idx] || "pos-top";
        const isActive = data.turn === p;
        const handCount = (data.hands[p] || []).length;
        const hasPassed = (data.passed || []).includes(p);
        const zone = document.createElement("div");
        zone.className = `opp-zone ${pos}${isActive ? " active-zone" : ""}`;
        const name = document.createElement("div");
        name.className = `opp-name${isActive ? " their-turn" : ""}`;
        name.textContent = p;
        zone.appendChild(name);
        const countEl = document.createElement("div");
        countEl.className = "opp-count";
        countEl.textContent = `${handCount} card${handCount !== 1 ? "s" : ""}${hasPassed ? " · passed" : ""}`;
        zone.appendChild(countEl);
        const row = document.createElement("div");
        row.className = "opp-hand-row";
        const show = Math.min(handCount, 8);
        for (let i = 0; i < show; i++) {
            const c = document.createElement("div");
            c.className = "opp-hand-card";
            row.appendChild(c);
        }
        if (handCount > 8) {
            const m = document.createElement("span");
            m.className = "opp-more";
            m.textContent = `+${handCount - 8}`;
            row.appendChild(m);
        }
        zone.appendChild(row);
        oppContainer.appendChild(zone);
    });

    document.getElementById("turn-pill").classList.toggle("visible", myTurn);

    const handEl = document.getElementById("your-hand");
    handEl.innerHTML = "";
    const sorted = [...hand].sort((a, b) => {
        const si = SUITS.indexOf(getSuit(a)) - SUITS.indexOf(getSuit(b));
        if (si !== 0) return si;
        return rankVal(a) - rankVal(b);
    });
    sorted.forEach(card => {
        const isPlayable = playable.includes(card);
        const d = document.createElement("div");
        d.className = `hcard${!isPlayable || !myTurn ? " dim" : ""}${isPlayable && myTurn ? " playable" : ""}`;
        d.style.backgroundImage = cardImg(card);
        if (isPlayable && myTurn) d.onclick = () => playCard(card);
        handEl.appendChild(d);
    });

    const passBtn = document.getElementById("pass-btn");
    passBtn.style.display = (myTurn && playable.length === 0 && hand.length > 0) ? "block" : "none";

    const finBar = document.getElementById("finished-bar");
    const finished = data.finished || [];
    finBar.innerHTML = finished.map((p, i) =>
        `<div class="fin-badge">${["🥇", "🥈", "🥉"][i] || "•"} ${p}</div>`
    ).join("");

    if (phase === "done") showNotif(`Game over! Winner: ${finished[0]}`, 8000);
}