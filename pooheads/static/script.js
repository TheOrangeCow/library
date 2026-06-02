const socket = io();
let selectedCards = [];
let currentPile = [];
let pendingAceCards = null;
let lastState = null;
let swapHandPick = null;
let swapFacePick = null;
let swapTimerVal = 20;
let swapTimerInterval = null;
let myReady = false;
const chatsendid = "send_game_msg";
const chatreceiveid = "receive_game_msg";

const RANK_ORDER = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "JOKER"];

const OPP_SLOTS = [
    ["pos-top"],
    ["pos-left", "pos-right"],
    ["pos-left", "pos-top", "pos-right"],
    ["pos-topleft", "pos-top", "pos-topright", "pos-right"],
    ["pos-left", "pos-topleft", "pos-top", "pos-topright", "pos-right"],
];

function sortCards(cards) {
    return [...cards].sort((a, b) => RANK_ORDER.indexOf(getRank(a)) - RANK_ORDER.indexOf(getRank(b)));
}
function getRank(card) {
    if (card.includes("JOKER")) return "JOKER";
    return card.replace(/[^0-9JQKA]/g, "");
}
function cardImg(card) { return `url('/static/cards/${card}.png')`; }
function getRankVal(card) {
    const r = getRank(card);
    if (r === "JOKER") return 0; if (r === "A") return 14;
    if (r === "J") return 11; if (r === "Q") return 12; if (r === "K") return 13;
    const n = parseInt(r); return isNaN(n) ? 0 : n;
}
function getTopValue(data) {
    const pile = data.pile || [];
    for (let i = pile.length - 1; i >= 0; i--) {
        const r = getRank(pile[i]);
        if (r !== "3" && r !== "JOKER") {
            if (r === "A") return data.aceMode === "low" ? 1 : 14;
            return getRankVal(pile[i]);
        }
    }
    return null;
}
function cardIsPlayable(card, data) {
    const r = getRank(card);
    if (r === "JOKER") return true;
    if (r === "2" || r === "3") return true;
    if (data.sevenRule) {
        if (r === "10" || r === "8") return false;
        return r === "A" ? true : getRankVal(card) <= 7;
    }
    if (r === "10") return true;
    const topV = getTopValue(data);
    if (r === "A") return true;
    if (topV !== null && getRankVal(card) < topV) return false;
    return true;
}
function isMyTurn(data) { return data.turn === username; }

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
        const count = played.length;
        const desc = count > 1 ? `${count}× <b>${r}</b>` : `a <b>${r}</b>`;
        const who = actor === username ? "<span class='fp'>You</span>" : `<span class='fp'>${actor}</span>`;
        showFeedToast(`${who} played ${desc}`);
    } else if (newPile.length === 0 && oldPile.length > 0) {
        const myOld = (lastState.hands?.[actor] || []).length;
        const myNew = (newState.hands?.[actor] || []).length;
        const who = actor === username ? "<span class='fp'>You</span>" : `<span class='fp'>${actor}</span>`;
        if (myNew > myOld) {
            showFeedToast(`${who} picked up the pile`);
        } else {
            showFeedToast(`${who} burned the pile`);
        }
    }
}

socket.on("connect", () => {
    socket.emit("join", { code: roomCode, username });
    socket.emit("set_page", { page: `Gaming:${roomCode}` });
});
socket.on("state", (data) => { detectPlays(data); render(data); });
socket.on("invalidPlay", (data) => { showNotif(data.msg || "Can't play that!"); selectedCards = []; renderLastState(); });

function startGame() {
    socket.emit("start", { code: roomCode }); 
    const addBotBtn = document.getElementById("addBotBtn");
    if (addBotBtn) {
        addBotBtn.disabled = g.players.length >= 6 || g.phase !== "lobby";
    }
}
function copyLink() { navigator.clipboard.writeText(window.location.href); showNotif("Link copied!"); }

function playSelected() {
    if (!selectedCards.length) return;
    const ranks = selectedCards.map(c => getRank(c));
    if (new Set(ranks).size === 1 && ranks[0] === "A") {
        pendingAceCards = [...selectedCards]; selectedCards = [];
        document.getElementById("aceModal").classList.add("open"); return;
    }
    dispatchPlay(selectedCards, "high"); selectedCards = [];
}
function playCard(card) {
    if (getRank(card) === "A") { pendingAceCards = [card]; document.getElementById("aceModal").classList.add("open"); return; }
    dispatchPlay([card], "high");
}
function confirmAce(mode) {
    document.getElementById("aceModal").classList.remove("open");
    if (!pendingAceCards) return;
    dispatchPlay(pendingAceCards, mode); pendingAceCards = null;
}
function dispatchPlay(cards, aceMode) {
    socket.emit("play", { code: roomCode, username, cards, aceMode }); selectedCards = [];
}
function pickupPile() { socket.emit("pickup", { code: roomCode, username }); }

function openSwapPhase() {
    document.getElementById("swapOverlay").classList.add("open");
    swapHandPick = null; swapFacePick = null; myReady = false;
    document.getElementById("readyBtn").disabled = false;
    if (swapTimerInterval) clearInterval(swapTimerInterval);
    swapTimerVal = 20; renderSwapTimer();
    swapTimerInterval = setInterval(() => {
        swapTimerVal--; renderSwapTimer();
        if (swapTimerVal <= 0) { clearInterval(swapTimerInterval); swapTimerInterval = null; }
    }, 1000);
}
function closeSwapPhase() {
    document.getElementById("swapOverlay").classList.remove("open");
    if (swapTimerInterval) { clearInterval(swapTimerInterval); swapTimerInterval = null; }
}
function renderSwapTimer() {
    const el = document.getElementById("swapTimer");
    el.textContent = swapTimerVal;
    el.classList.toggle("urgent", swapTimerVal <= 5);
}
function renderSwapCards(data) {
    const hc = data.hands?.[username] || [];
    const fc = data.faceup?.[username] || [];
    const hEl = document.getElementById("swapHandCards");
    const fEl = document.getElementById("swapFaceCards");
    hEl.innerHTML = ""; fEl.innerHTML = "";
    hc.forEach(c => {
        const d = document.createElement("div");
        d.className = "swap-card" + (swapHandPick === c ? " sel-hand" : "");
        d.style.backgroundImage = cardImg(c); d.onclick = () => pickSwapHand(c); hEl.appendChild(d);
    });
    fc.forEach(c => {
        const d = document.createElement("div");
        d.className = "swap-card" + (swapFacePick === c ? " sel-face" : "");
        d.style.backgroundImage = cardImg(c); d.onclick = () => pickSwapFace(c); fEl.appendChild(d);
    });
    const ready = data.swapReady || [];
    document.getElementById("swapReadyList").innerHTML =
        (data.players || []).map(p => `<span class="${ready.includes(p) ? 'rdy' : ''}">${ready.includes(p) ? '✓' : '○'} ${p}</span>`).join("  ");
    const hint = document.getElementById("swapHint");
    hint.textContent = !swapHandPick ? "Pick a hand card…" : !swapFacePick ? "Now pick a face-up card." : "";
}
function pickSwapHand(c) { if (myReady) return; swapHandPick = swapHandPick === c ? null : c; renderSwapCards(lastState); trySwap(); }
function pickSwapFace(c) { if (myReady) return; swapFacePick = swapFacePick === c ? null : c; renderSwapCards(lastState); trySwap(); }

function trySwap() {
    if (!swapHandPick || !swapFacePick) return;
    socket.emit("swap", { code: roomCode, username, handCard: swapHandPick, faceCard: swapFacePick });
    swapHandPick = null; swapFacePick = null;
}
function markReady() {
    if (myReady) return; myReady = true;
    document.getElementById("readyBtn").disabled = true;
    socket.emit("swapReady", { code: roomCode, username });
}

function toggleCard(card) {
    const idx = selectedCards.indexOf(card);
    if (idx === -1) {
        if (selectedCards.length && getRank(selectedCards[0]) !== getRank(card)) { showNotif("Same rank only!"); return; }
        selectedCards.push(card);
    } else selectedCards.splice(idx, 1);
    renderLastState();
}

function showNotif(msg, dur = 2500) {
    const el = document.getElementById("notif");
    el.textContent = msg; el.style.display = "block";
    clearTimeout(el._t); el._t = setTimeout(() => el.style.display = "none", dur);
}

function render(data) {
    lastState = data;
    const phase = data.phase || "playing";
    if (phase === "swap") {
        if (!document.getElementById("swapOverlay").classList.contains("open")) openSwapPhase();
        renderSwapCards(data); return;
    }
    if (document.getElementById("swapOverlay").classList.contains("open")) {
        closeSwapPhase(); showNotif("Game on!");
    }
    renderLastState();
}

function renderLastState() {
    const data = lastState;
    if (!data) return;
    currentPile = data.pile || [];
    const myTurn = isMyTurn(data);
    const you = username;
    const myHand = data.hands?.[you] || [];
    const myFU = data.faceup?.[you] || [];
    const myFD = data.facedown?.[you] || [];

    const pileEl = document.getElementById("pile-cards");
    if (currentPile.length === 0) {
        pileEl.innerHTML = `<div class="pile-empty-slot">empty</div>`;
    } else {
        const shown = currentPile.slice(-3);
        pileEl.innerHTML = shown.map(c => `<div class="pile-card" style="background-image:${cardImg(c)}"></div>`).join("");
    }
    document.getElementById("pile-count").textContent =
        currentPile.length > 0 ? `${currentPile.length} card${currentPile.length !== 1 ? 's' : ''}` : "";

    const ruleEl = document.getElementById("ruleIndicator");
    if (data.sevenRule) { ruleEl.textContent = "7 or lower only"; }
    else if (data.afterTwo) { ruleEl.textContent = "Reset - 2 played"; }
    else {
        let er = null;
        for (let i = currentPile.length - 1; i >= 0; i--) { const r = getRank(currentPile[i]); if (r !== "3" && r !== "JOKER") { er = r; break; } }
        ruleEl.textContent = er === "A" ? `Ace as ${data.aceMode === "low" ? "1 (Low)" : "14 (High)"}` : "";
    }

    const histEl = document.getElementById("pileHistory");
    const history = data.pileHistory || [];
    if (history.length && currentPile.length) {
        const topRank = getRank(currentPile[currentPile.length - 1]);
        let html = history.slice(-3).map((e, i, arr) => {
            const last = i === arr.length - 1;
            const an = e.aceMode ? ` (${e.aceMode === "low" ? "1" : "14"})` : "";
            return `<span class="ph-entry${last ? " latest" : ""}">${e.cards.join(", ")}${an}</span>`;
        }).join("");
        if (topRank === "3" || topRank === "JOKER") {
            const last = history[history.length - 1];
            if (last) {
                const cover = topRank === "JOKER" ? "Joker" : "3";
                const an = last.aceMode ? ` as ${last.aceMode === "low" ? "1" : "14"}` : "";
                html += `<span class="ph-acting">↳ acting as ${last.rank}${an} (${cover})</span>`;
            }
        }
        histEl.innerHTML = html;
    } else histEl.innerHTML = "";

    const showPickup = myTurn && currentPile.length > 0 && myHand.length > 0 && !myHand.some(c => cardIsPlayable(c, data));
    document.getElementById("pickupBtn").style.display = showPickup ? "block" : "none";

    document.getElementById("turn-pill").classList.toggle("visible", myTurn);

    const oppContainer = document.getElementById("opp-container");
    oppContainer.innerHTML = "";
    const opponents = Object.keys(data.hands || {}).filter(p => p !== you);
    const slots = opponents.length >= 1 && opponents.length <= 5
        ? OPP_SLOTS[opponents.length - 1]
        : opponents.map((_, i) => ["pos-top", "pos-left", "pos-right", "pos-topleft", "pos-topright"][i % 5]);

    opponents.forEach((p, idx) => {
        const pos = slots[idx] || "pos-top";
        const isActive = data.turn === p;
        const handCount = (data.hands[p] || []).length;
        const fuCards = data.faceup?.[p] || [];
        const fdCount = (data.facedown?.[p] || []).length;
        const stackCount = Math.max(fuCards.length, fdCount);

        const zone = document.createElement("div");
        zone.className = `opp-zone ${pos}${isActive ? " active-zone" : ""}`;

        const name = document.createElement("div");
        name.className = `opp-name${isActive ? " their-turn" : ""}`;
        name.textContent = p;
        zone.appendChild(name);

        if (handCount > 0) {
            const row = document.createElement("div");
            row.className = "opp-hand-row";
            const show = Math.min(handCount, 7);
            for (let i = 0; i < show; i++) { const c = document.createElement("div"); c.className = "opp-hand-card"; row.appendChild(c); }
            if (handCount > 7) { const m = document.createElement("span"); m.className = "opp-more"; m.textContent = `+${handCount - 7}`; row.appendChild(m); }
            zone.appendChild(row);
        }

        const cardsRow = document.createElement("div");
        cardsRow.className = "opp-cards";
        for (let i = 0; i < stackCount; i++) {
            const st = document.createElement("div");
            st.className = "opp-stack";
            if (i < fdCount) { const fd = document.createElement("div"); fd.className = "opp-fd"; st.appendChild(fd); }
            if (i < fuCards.length) { const fu = document.createElement("div"); fu.className = "opp-fu"; fu.style.backgroundImage = cardImg(fuCards[i]); st.appendChild(fu); }
            cardsRow.appendChild(st);
        }
        zone.appendChild(cardsRow);
        oppContainer.appendChild(zone);
    });

    const tableEl = document.getElementById("your-table-cards");
    tableEl.innerHTML = "";
    const stackCount = Math.max(myFU.length, myFD.length);
    const canFU = myTurn && myHand.length === 0;
    const canFD = myTurn && myHand.length === 0 && myFU.length === 0;

    for (let i = 0; i < stackCount; i++) {
        const hasFD = i < myFD.length;
        const hasFU = i < myFU.length;
        const fdOnly = hasFD && !hasFU;

        const st = document.createElement("div");
        st.className = `your-stack${fdOnly ? " fd-only" : ""}${(canFU || canFD) ? " can-play" : ""}`;

        if (hasFD) {
            const fd = document.createElement("div");
            fd.className = "sfd";
            if (canFD) { fd.onclick = () => playCard(myFD[i]); st.style.cursor = "pointer"; }
            st.appendChild(fd);
        }
        if (hasFU) {
            const fu = document.createElement("div");
            fu.className = "sfu";
            fu.style.backgroundImage = cardImg(myFU[i]);
            if (canFU) { fu.onclick = () => playCard(myFU[i]); st.style.cursor = "pointer"; }
            st.appendChild(fu);
        }
        tableEl.appendChild(st);
    }

    const handEl = document.getElementById("your-hand");
    handEl.innerHTML = "";
    sortCards(myHand).forEach(c => {
        const d = document.createElement("div");
        d.className = `hcard${selectedCards.includes(c) ? " sel" : ""}${!myTurn ? " dim" : ""}`;
        d.style.backgroundImage = cardImg(c);
        if (myTurn) d.onclick = () => toggleCard(c);
        handEl.appendChild(d);
    });

    const playBtn = document.getElementById("play-btn");
    if (myTurn && selectedCards.length > 0) {
        const r = getRank(selectedCards[0]);
        const cnt = selectedCards.length;
        playBtn.textContent = `▶ Play ${cnt > 1 ? cnt + "× " : ""}${r}`;
        playBtn.style.display = "inline-block";
    } else playBtn.style.display = "none";

    const finBar = document.getElementById("finished-bar");
    const dead = data.dead || [];
    finBar.innerHTML = dead.map((p, i) => `<div class="fin-badge">${["🥇", "🥈", "🥉"][i] || "•"} ${p}</div>`).join("");
}

function addBot() {
    socket.emit("add_bot", { code: roomCode, username: username });
}