const socket = io();
let lastState = null;
let pendingAceFlip = false;

function getRank(card) {
    if (card.includes("JOKER")) return "JOKER";
    return card.replace(/[^0-9JQKA]/g, "");
}

function cardImg(card) { 
    return `url('/static/cards/${card}.png')`; 
}

function showNotif(msg, dur = 2500) {
    const el = document.getElementById("notif");
    el.textContent = msg;
    el.style.display = "block";
    clearTimeout(el._t);
    el._t = setTimeout(() => el.style.display = "none", dur);
}

function copyLink() {
    navigator.clipboard.writeText(window.location.href);
    showNotif("Link copied!");
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

function detectPlays(newState) {
    if (!lastState) return;
    const oldPile = lastState.pile || [];
    const newPile = newState.pile || [];
    const actor = lastState.turn;
    if (!actor) return;

    if (newPile.length > oldPile.length) {
        const played = newPile.slice(oldPile.length);
        const r = getRank(played[0]);
        const who = actor === username ? "<span class='fp'>You</span>" : `<span class='fp'>${actor}</span>`;
        showFeedToast(`${who} played a <b>${r}</b>`);
    } else if (newPile.length === 0 && oldPile.length > 0) {
        const oldCount = (lastState.piles?.[actor] || []).length;
        const newCount = (newState.piles?.[actor] || []).length;
        const who = actor === username ? "<span class='fp'>You</span>" : `<span class='fp'>${actor}</span>`;
        showFeedToast(newCount > oldCount ? `${who} picked up the pile` : `${who} burned the pile`);
    }
}


socket.on("connect", () => {
    socket.emit("enraged_join", { code: roomCode, username });
    socket.emit("set_page", { page: `Gaming:${roomCode}` });
});

socket.on("enraged_state", (data) => {
    detectPlays(data);
    lastState = data;
    render(data);
});

socket.on("enraged_invalid", (data) => {
    showNotif(data.msg || "Invalid play!");
});

socket.on("enraged_receive_msg", (data) => {
    const msgDiv = document.getElementById("chat-messages");
    msgDiv.appendChild(buildMessage(data.msg, data.sender === username));
    msgDiv.scrollTop = msgDiv.scrollHeight;
});


function startGame() {
    socket.emit("enraged_start", { code: roomCode });
}

function doShuffle() {
    if (!lastState || lastState.turn !== username) return;
    if (lastState.shuffledThisTurn) { showNotif("Already shuffled this turn!"); return; }
    socket.emit("enraged_shuffle", { code: roomCode, username });
}

function doFlip() {
    if (!lastState || lastState.turn !== username) return;
    const myPile = lastState.piles?.[username] || [];
    if (!myPile.length) { showNotif("Your pile is empty!"); return; }

    const topCard = myPile[myPile.length - 1];
    const r = getRank(topCard);

    if (r === "A") {
        pendingAceFlip = true;
        document.getElementById("aceModal").classList.add("open");
        return;
    }

    socket.emit("enraged_play", { code: roomCode, username, aceMode: "high" });
}

function confirmAce(mode) {
    document.getElementById("aceModal").classList.remove("open");
    if (!pendingAceFlip) return;
    pendingAceFlip = false;
    socket.emit("enraged_play", { code: roomCode, username, aceMode: mode });
}

function doPickup() {
    if (!lastState || lastState.turn !== username) return;
    socket.emit("enraged_pickup", { code: roomCode, username });
}


const OPP_SLOTS = [
    ["pos-top"],
    ["pos-left", "pos-right"],
    ["pos-left", "pos-top", "pos-right"],
    ["pos-topleft", "pos-top", "pos-topright", "pos-right"],
    ["pos-left", "pos-topleft", "pos-top", "pos-topright", "pos-right"],
];

function render(data) {
    const myTurn = data.turn === username;
    const myPile = data.piles?.[username] || [];
    const centerPile = data.pile || [];

    const pileEl = document.getElementById("pile-cards");
    if (centerPile.length === 0) {
        pileEl.innerHTML = `<div class="pile-empty-slot">empty</div>`;
    } else {
        const shown = centerPile.slice(-3);
        pileEl.innerHTML = shown.map(c =>
            `<div class="pile-card" style="background-image:${cardImg(c)}"></div>`
        ).join("");
    }
    document.getElementById("pile-count").textContent =
        centerPile.length > 0 ? `${centerPile.length} card${centerPile.length !== 1 ? "s" : ""}` : "";

    const ruleEl = document.getElementById("ruleIndicator");
    if (data.sevenRule) ruleEl.textContent = "7 or lower only";
    else if (data.afterTwo) ruleEl.textContent = "Reset - 2 played";
    else {
        let er = null;
        for (let i = centerPile.length - 1; i >= 0; i--) {
            const r = getRank(centerPile[i]);
            if (r !== "3" && r !== "JOKER") { er = r; break; }
        }
        ruleEl.textContent = er === "A"
            ? `Ace as ${data.aceMode === "low" ? "1 (Low)" : "14 (High)"}`
            : "";
    }

    const histEl = document.getElementById("pileHistory");
    const history = data.pileHistory || [];
    if (history.length && centerPile.length) {
        histEl.innerHTML = history.slice(-3).map((e, i, arr) => {
            const last = i === arr.length - 1;
            const an = e.aceMode ? ` (${e.aceMode === "low" ? "1" : "14"})` : "";
            return `<span class="ph-entry${last ? " latest" : ""}">${e.cards.join(", ")}${an}</span>`;
        }).join("");
    } else histEl.innerHTML = "";

    document.getElementById("turn-pill").classList.toggle("visible", myTurn);

    const stackEl = document.getElementById("your-pile-stack");
    stackEl.innerHTML = "";
    const show = Math.min(myPile.length, 5);
    for (let i = 0; i < show; i++) {
        const d = document.createElement("div");
        d.className = "pile-back-card";
        d.style.bottom = `${i * 4}px`;
        d.style.left = `${i * 2}px`;
        stackEl.appendChild(d);
    }
    document.getElementById("your-pile-count").textContent =
        `${myPile.length} card${myPile.length !== 1 ? "s" : ""} in your pile`;

    const flipBtn = document.getElementById("flip-btn");
    const shuffleBtn = document.getElementById("shuffle-btn");

    flipBtn.disabled = !myTurn || myPile.length === 0;
    shuffleBtn.disabled = !myTurn || data.shuffledThisTurn || myPile.length === 0;
    shuffleBtn.title = data.shuffledThisTurn ? "Already shuffled this turn" : "Shuffle your pile"

    const oppContainer = document.getElementById("opp-container");
    oppContainer.innerHTML = "";
    const opponents = Object.keys(data.piles || {}).filter(p => p !== username);
    const slots = opponents.length >= 1 && opponents.length <= 5
        ? OPP_SLOTS[opponents.length - 1]
        : opponents.map((_, i) => ["pos-top", "pos-left", "pos-right", "pos-topleft", "pos-topright"][i % 5]);

    opponents.forEach((p, idx) => {
        const pos = slots[idx] || "pos-top";
        const isActive = data.turn === p;
        const count = (data.piles[p] || []).length;

        const zone = document.createElement("div");
        zone.className = `opp-zone ${pos}${isActive ? " active-zone" : ""}`;

        const name = document.createElement("div");
        name.className = `opp-name${isActive ? " their-turn" : ""}`;
        name.textContent = p;
        zone.appendChild(name);

        const miniStack = document.createElement("div");
        miniStack.className = "opp-mini-stack";
        const miniShow = Math.min(count, 4);
        for (let i = 0; i < miniShow; i++) {
            const c = document.createElement("div");
            c.className = "opp-pile-back";
            c.style.bottom = `${i * 3}px`;
            c.style.left = `${i * 2}px`;
            miniStack.appendChild(c);
        }
        zone.appendChild(miniStack);

        const countEl = document.createElement("div");
        countEl.className = "opp-pile-count";
        countEl.textContent = `${count} cards`;
        zone.appendChild(countEl);

        oppContainer.appendChild(zone);
    });

    const finBar = document.getElementById("finished-bar");
    const dead = data.dead || [];
    finBar.innerHTML = dead.map((p, i) =>
        `<div class="fin-badge">${["🥇", "🥈", "🥉"][i] || "•"} ${p}</div>`
    ).join("");

}


function sendMessage() {
    const input = document.getElementById("chat-input");
    const msg = input.value.trim();
    if (!msg) return;
    socket.emit("enraged_game_msg", { msg, code: roomCode });
    input.value = "";
}

function resetChat() {
    document.getElementById("chat-messages").innerHTML = "";
}

document.getElementById("chat-send").onclick = sendMessage;
document.getElementById("chat-input").onkeydown = e => { if (e.key === "Enter") sendMessage(); };

document.addEventListener("visibilitychange", () => {
    socket.emit(document.visibilityState === "hidden" ? "tab_hidden" : "tab_visible");
});


const dragItem = document.getElementById("chat-container");
const dragHeader = document.getElementById("chat-header");
let active = false, currentX, currentY, initialX, initialY, xOffset = 0, yOffset = 0;

dragHeader.onmousedown = (e) => {
    initialX = e.clientX - xOffset;
    initialY = e.clientY - yOffset;
    active = true;
};
document.onmouseup = () => active = false;
document.onmousemove = (e) => {
    if (active) {
        e.preventDefault();
        currentX = e.clientX - initialX;
        currentY = e.clientY - initialY;
        xOffset = currentX; yOffset = currentY;
        dragItem.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
    }
};