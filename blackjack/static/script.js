const socket = io();
let lastState = null;

const OPP_SLOTS = [
    ["pos-left-2"],
    ["pos-left-2", "pos-right-2"],
    ["pos-left-1", "pos-left-3", "pos-right-2"],
    ["pos-left-1", "pos-left-3", "pos-right-1", "pos-right-3"],
    ["pos-left-1", "pos-left-2", "pos-left-3", "pos-right-1", "pos-right-3"],
    ["pos-left-1", "pos-left-2", "pos-left-3", "pos-right-1", "pos-right-2", "pos-right-3"],
];

const CHIP_DENOMS = [100, 50, 25, 10, 5, 1];
const CHIP_COLORS = {
    100: "chip-100", 50: "chip-50", 25: "chip-25",
    10:  "chip-10",   5: "chip-5",   1: "chip-1"
};

function cardImg(c) {
    if (c === "back") return "url('/static/cards/back.png')";
    return `url('/static/cards/${c}.png')`;
}

function handTotal(hand) {
    let total = 0, aces = 0;
    for (const c of hand) {
        if (c === "back") continue;
        const r = c.slice(0, -1);
        if (r === "A")                        { total += 11; aces++; }
        else if (["J","Q","K"].includes(r))    total += 10;
        else                                   total += parseInt(r);
    }
    while (total > 21 && aces) { total -= 10; aces--; }
    return total;
}

function showNotif(msg, dur=2500) {
    const el = document.getElementById("notif");
    el.textContent = msg; el.style.display = "block";
    clearTimeout(el._t); el._t = setTimeout(() => el.style.display="none", dur);
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

function makeChipStack(amount) {
    const wrap = document.createElement("div");
    wrap.className = "chip-stack";
    let remaining = amount;
    const chips = [];
    for (const denom of CHIP_DENOMS) {
        while (remaining >= denom) { chips.push(denom); remaining -= denom; }
    }
    const shown = chips.slice(0, 7);
    shown.forEach((denom, i) => {
        const c = document.createElement("div");
        c.className = `chip ${CHIP_COLORS[denom]}`;
        c.style.left  = (i * 5) + "px";
        c.style.animationDelay = (i * 0.07) + "s";
        c.textContent = denom >= 10 ? denom : "";
        wrap.appendChild(c);
    });
    wrap.style.width = (shown.length * 5 + 20) + "px";
    return wrap;
}

socket.on("connect", () => socket.emit("bj_join", { code: roomCode, username }));
socket.on("bj_state", (data) => { lastState = data; render(data); });
socket.on("bj_error", (data) => showNotif(data.msg));

function placeBet() {
    const val = parseInt(document.getElementById("bet-input").value);
    if (!val || val < 1) { showNotif("Enter a valid bet."); return; }
    socket.emit("bj_bet", { code: roomCode, username, amount: val });
}

function quickBet(amount) {
    document.getElementById("bet-input").value = amount;
    socket.emit("bj_bet", { code: roomCode, username, amount });
}

function doHit() { socket.emit("bj_hit", { code: roomCode, username }); }
function doStand() { socket.emit("bj_stand", { code: roomCode, username }); }
function doDouble() { socket.emit("bj_double", { code: roomCode, username }); }
function newRound() { socket.emit("bj_new_round", { code: roomCode, username }); }

function renderCards(hand, container, small=false) {
    const existing = container.children.length;
    const incoming = (hand || []).length;
    if (existing === incoming) return;
    container.innerHTML = "";
    (hand || []).forEach((c, i) => {
        const d = document.createElement("div");
        d.className = small ? "opp-bj-card" : "bj-card";
        d.style.backgroundImage = cardImg(c);
        d.style.animationDelay  = (i * 0.12) + "s";
        container.appendChild(d);
    });
}

function render(data) {
    const phase    = data.phase;
    const myHand   = data.hands?.[username]  || [];
    const myStatus = data.status?.[username];
    const myChips  = data.chips?.[username]  ?? 0;
    const myBet    = data.bets?.[username]   ?? 0;
    const myTurn   = data.turn === username;
    const results  = data.results || {};
    const myResult = results[username];

    const dealerHand = (phase === "playing")
        ? (data.dealer_hand_visible || [])
        : (data.dealer_hand || []);
    renderCards(dealerHand, document.getElementById("dealer-hand"));
    const dealerTotalEl = document.getElementById("dealer-total");
    if (phase === "done" || phase === "dealer") {
        const dt = handTotal(data.dealer_hand || []);
        dealerTotalEl.textContent = `${dt}${dt > 21 ? " BUST" : ""}`;
    } else {
        const v = dealerHand[0] ? handTotal([dealerHand[0]]) : "";
        dealerTotalEl.textContent = v ? `${v} + ?` : "";
    }

    renderCards(myHand, document.getElementById("your-hand"));
    const myTotal = handTotal(myHand);
    document.getElementById("your-total").textContent =
        myHand.length ? `${myTotal}${myTotal > 21 ? " BUST" : ""}` : "";

    const chipsEl = document.getElementById("your-chips");
    chipsEl.innerHTML = `<span>Chips: ${myChips}</span>`;
    if (myBet > 0) {
        const bl = document.createElement("span");
        bl.textContent = `Bet: ${myBet}`;
        chipsEl.appendChild(bl);
        chipsEl.appendChild(makeChipStack(myBet));
    }

    document.getElementById("turn-pill").classList.toggle("visible", myTurn);

    const betArea     = document.getElementById("bet-area");
    const playArea    = document.getElementById("play-area");
    const newRoundBtn = document.getElementById("new-round-btn");
    betArea.style.display     = "none";
    playArea.style.display    = "none";
    newRoundBtn.style.display = "none";

    if (phase === "betting" && myStatus === "waiting") {
        betArea.style.display = "flex";
    } else if (phase === "playing" && myTurn && myStatus === "playing") {
        playArea.style.display = "flex";
        document.getElementById("double-btn").style.display =
            myHand.length === 2 ? "inline-block" : "none";
    } else if (phase === "done") {
        newRoundBtn.style.display = "block";
    }

    const banner = document.getElementById("result-banner");
    if (phase === "done" && myResult) {
        const r = myResult.result;
        const msgs = {
            blackjack: `Blackjack! +${myResult.winnings}`,
            win:  `✓ Win! +${myResult.winnings}`,
            push: `↔ Push`,
            lose: `✗ Lose`,
            bust: `✗ Bust`,
        };
        if (!banner.textContent) {
            banner.textContent = msgs[r] || "";
            banner.className   = `result-${r === "blackjack" ? "blackjack" : r} result-win-anim`;
            showFeedToast(`<span class="fp">${username}</span> - ${msgs[r]}`);
        }
    } else if (phase !== "done") {
        banner.textContent = "";
        banner.className   = "";
    }

    const oppContainer = document.getElementById("opp-container");
    oppContainer.innerHTML = "";
    const others = (data.players || []).filter(p => p !== username);
    const slots  = OPP_SLOTS[Math.min(others.length - 1, 5)] || [];

    others.forEach((p, idx) => {
        const pos      = slots[idx] || "pos-left-1";
        const isActive = data.turn === p;
        const pBet     = data.bets?.[p]   ?? 0;
        const pChips   = data.chips?.[p]  ?? 0;
        const pHand    = data.hands?.[p]  || [];
        const pResult  = results[p];
        const pStatus  = data.status?.[p] || "";

        const zone = document.createElement("div");
        zone.className = `opp-zone ${pos}${isActive ? " active-zone" : ""}`;

        const name = document.createElement("div");
        name.className = `opp-name${isActive ? " their-turn" : ""}`;
        name.textContent = p;
        zone.appendChild(name);

        const betLbl = document.createElement("div");
        betLbl.className = "opp-bet-label";
        betLbl.textContent = `${pChips} chips${pBet ? ` · bet ${pBet}` : ""}`;
        zone.appendChild(betLbl);

        if (pBet > 0) zone.appendChild(makeChipStack(pBet));

        const cardRow = document.createElement("div");
        cardRow.className = "opp-cards-row";
        pHand.forEach((c, i) => {
            const d = document.createElement("div");
            d.className = "opp-bj-card";
            d.style.backgroundImage = cardImg(c);
            d.style.animationDelay  = (i * 0.1) + "s";
            cardRow.appendChild(d);
        });
        zone.appendChild(cardRow);

        if (phase === "done" && pResult) {
            const st = document.createElement("div");
            const r = pResult.result;
            st.className = `opp-status ${r}`;
            const labels = { win:"WIN", lose:"LOSE", push:"PUSH", bust:"BUST", blackjack:"BLACKJACK" };
            st.textContent = labels[r] || r.toUpperCase();
            zone.appendChild(st);
        } else if (pStatus && pStatus !== "waiting" && pStatus !== "bet_placed") {
            const st = document.createElement("div");
            st.className = "opp-status";
            st.textContent = pStatus.replace("_"," ").toUpperCase();
            zone.appendChild(st);
        }

        oppContainer.appendChild(zone);
    });
}