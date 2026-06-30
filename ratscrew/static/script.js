const socket = io();
let lastState = null;
const chatsendid = "send_game_msg";
const chatreceiveid = "receive_game_msg";

const OPP_SLOTS = [
    ["pos-top"],
    ["pos-left", "pos-right"],
    ["pos-left", "pos-top", "pos-right"],
    ["pos-topleft", "pos-top", "pos-topright", "pos-right"],
    ["pos-left", "pos-topleft", "pos-top", "pos-topright", "pos-right"],
];

function getRank(card) {
    return card.replace(/[^0-9JQKA]/g, "");
}
function cardImg(card) { return `url('/static/cards/${card}.png')`; }
function isMyTurn(data) { return data.turn === username; }

function showFeedToast(html, cls) {
    const feed = document.getElementById("play-feed");
    const el = document.createElement("div");
    el.className = "feed-toast" + (cls ? " " + cls : "");
    el.innerHTML = html;
    feed.appendChild(el);
    while (feed.children.length > 5) feed.removeChild(feed.firstChild);
    setTimeout(() => {
        el.classList.add("bye");
        setTimeout(() => el.remove(), 380);
    }, 3500);
}

function detectPlays(newState) {
    if (!lastState) return;
    const oldCenter = lastState.center || [];
    const newCenter = newState.center || [];

    if (newCenter.length > oldCenter.length) {
        const played = newCenter[newCenter.length - 1];
        const r = getRank(played);
        const actor = lastState.turn;
        if (actor) {
            const who = actor === username ? "<span class='fp'>You</span>" : `<span class='fp'>${actor}</span>`;
            showFeedToast(`${who} played a <b>${r}</b>`);
        }
    } else if (newCenter.length === 0 && oldCenter.length > 0) {
        if (!newState._slapJustHappened) {
            const ch = lastState.challenge;
            if (ch && ch.owner) {
                const who = ch.owner === username ? "<span class='fp'>You</span>" : `<span class='fp'>${ch.owner}</span>`;
                showFeedToast(`${who} won the pile on a challenge!`);
            }
        }
    }

    const oldDead = lastState.dead || [];
    const newDead = newState.dead || [];
    if (newDead.length > oldDead.length) {
        const justOut = newDead[newDead.length - 1];
        const who = justOut === username ? "<span class='fp'>You</span>" : `<span class='fp'>${justOut}</span>`;
        showFeedToast(`${who} ran out of cards and is eliminated`);
    }
}

socket.on("connect", () => {
    socket.emit("join", { code: roomCode, username });
    socket.emit("set_page", { page: `Gaming:${roomCode}` });
});

socket.on("state", (data) => { detectPlays(data); render(data); });

socket.on("slapResult", (data) => {
    if (data.success) {
        const who = data.user === username ? "<span class='fp'>You</span>" : `<span class='fp'>${data.user}</span>`;
        showFeedToast(`${who} slapped the pile!`, "slap-good");
        if (data.user === username) showNotif("Nice slap!");
    } else {
        const who = data.user === username ? "<span class='fp'>You</span>" : `<span class='fp'>${data.user}</span>`;
        showFeedToast(`${who} slapped too soon — burned a card`, "slap-bad");
        if (data.user === username) showNotif("Bad slap! You burned a card.");
    }
});

function startGame() {
    socket.emit("start", { code: roomCode });
}
function copyLink() { navigator.clipboard.writeText(window.location.href); showNotif("Link copied!"); }
function addBot() { socket.emit("add_bot", { code: roomCode, username: username }); }

function playTop() {
    if (!lastState || lastState.turn !== username) return;
    socket.emit("play", { code: roomCode, username });
}

let slapCooldown = false;
function doSlap() {
    if (slapCooldown) return;
    if (!lastState || lastState.phase !== "playing") return;
    slapCooldown = true;
    const btn = document.getElementById("slapBtn");
    if (btn) {
        btn.classList.add("slapping");
        setTimeout(() => btn.classList.remove("slapping"), 150);
    }
    socket.emit("slap", { code: roomCode, username });
    setTimeout(() => { slapCooldown = false; }, 250);
}

document.addEventListener("keydown", (e) => {
    if (e.code === "Space") {
        const tag = (document.activeElement && document.activeElement.tagName) || "";
        if (tag === "INPUT" || tag === "TEXTAREA") return;
        e.preventDefault();
        doSlap();
    }
});

function showNotif(msg, dur = 2200) {
    const el = document.getElementById("notif");
    el.textContent = msg; el.style.display = "block";
    clearTimeout(el._t); el._t = setTimeout(() => el.style.display = "none", dur);
}

function render(data) {
    lastState = data;
    const myTurn = isMyTurn(data);
    const you = username;
    const center = data.center || [];

    const pileEl = document.getElementById("pile-cards");
    if (center.length === 0) {
        pileEl.innerHTML = `<div class="pile-empty-slot">empty</div>`;
    } else {
        const shown = center.slice(-3);
        pileEl.innerHTML = shown.map(c => `<div class="pile-card" style="background-image:${cardImg(c)}"></div>`).join("");
    }
    document.getElementById("pile-count").textContent =
        center.length > 0 ? `${center.length} card${center.length !== 1 ? 's' : ''}` : "";

    const chEl = document.getElementById("challengeIndicator");
    const ch = data.challenge;
    if (ch && ch.active) {
        const who = ch.owner === you ? "you" : ch.owner;
        chEl.textContent = `${ch.rank} played by ${who} — ${ch.count} card${ch.count !== 1 ? 's' : ''} to beat it`;
        chEl.classList.toggle("urgent", ch.count === 1);
    } else {
        chEl.textContent = "";
        chEl.classList.remove("urgent");
    }

    document.getElementById("turn-pill").classList.toggle("visible", myTurn && data.phase === "playing");

    const oppContainer = document.getElementById("opp-container");
    oppContainer.innerHTML = "";
    const allKnown = Array.from(new Set([...(data.players || []), ...(data.dead || [])]));
    const opponents = allKnown.filter(p => p !== you);
    const slots = opponents.length >= 1 && opponents.length <= 5
        ? OPP_SLOTS[opponents.length - 1]
        : opponents.map((_, i) => ["pos-top", "pos-left", "pos-right", "pos-topleft", "pos-topright"][i % 5]);

    opponents.forEach((p, idx) => {
        const pos = slots[idx] || "pos-top";
        const isActive = data.turn === p;
        const isDead = (data.dead || []).includes(p);
        const pileCount = (data.piles?.[p] || []).length;

        const zone = document.createElement("div");
        zone.className = `opp-zone ${pos}${isActive ? " active-zone" : ""}${isDead ? " eliminated" : ""}`;

        const name = document.createElement("div");
        name.className = `opp-name${isActive ? " their-turn" : ""}`;
        name.textContent = p;
        zone.appendChild(name);

        const stack = document.createElement("div");
        stack.className = "opp-pile-stack";
        if (pileCount > 0) {
            const back = document.createElement("div");
            back.className = "opp-pile-back";
            stack.appendChild(back);
        }
        zone.appendChild(stack);

        const cnt = document.createElement("div");
        cnt.className = "opp-pile-count";
        cnt.textContent = isDead ? "out" : `${pileCount} cards`;
        zone.appendChild(cnt);

        oppContainer.appendChild(zone);
    });

    const myPileCount = (data.piles?.[you] || []).length;
    const yourCardEl = document.getElementById("your-pile-card");
    yourCardEl.classList.toggle("can-play", myTurn && myPileCount > 0 && data.phase === "playing");
    yourCardEl.onclick = (myTurn && myPileCount > 0 && data.phase === "playing") ? playTop : null;
    document.getElementById("your-pile-count").textContent = `${myPileCount} cards`;

    const playBtn = document.getElementById("play-btn");
    playBtn.disabled = !(myTurn && myPileCount > 0 && data.phase === "playing");

    const finBar = document.getElementById("finished-bar");
    const dead = data.dead || [];
    finBar.innerHTML = dead.map((p, i) => `<div class="fin-badge">${["🥇", "🥈", "🥉"][i] || "•"} ${p} out</div>`).join("");

    const addBotBtn = document.getElementById("addBotBtn");
    if (addBotBtn) {
        addBotBtn.disabled = (data.players || []).length >= 6 || data.phase !== "lobby";
    }

    const winModal = document.getElementById("winModal");
    if (data.phase === "over" && data.winner) {
        document.getElementById("winTitle").textContent = data.winner === you ? "You Win!" : "Game Over";
        document.getElementById("winText").textContent = `${data.winner} took every card on the table.`;
        winModal.classList.add("open");
    } else {
        winModal.classList.remove("open");
    }
}