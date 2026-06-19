const socket = io();
let lastState = null;
const chatsendid = "white_game_msg";
const chatreceiveid = "white_receive_msg";

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
    if (c === "back") return `url('${previousCardBackURL}`;
    return `url('/static/cards/${c}.png')`;
}

function cardValue(c) {
    if (c === "back") return 0;
    const r = c.slice(0, -1);
    if (r === "A") return 1;
    if (["J", "Q", "K"].includes(r)) return 10;
    return parseInt(r);
}

function baseTotal(hand) {
    if (!hand || hand.length < 2) return (hand || []).reduce((s, c) => s + cardValue(c), 0);
    return cardValue(hand[0]) - cardValue(hand[1]);
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

socket.on("connect", () => {
    socket.emit("wj_join", { code: roomCode, username });
    socket.emit("set_page", { page: `Gaming:${roomCode}` });
});
socket.on("wj_state", (data) => { lastState = data; render(data); });
socket.on("wj_error", (data) => showNotif(data.msg));

function placeBet() {
    const val = parseInt(document.getElementById("bet-input").value);
    if (!val || val < 1) { showNotif("Enter a valid bet."); return; }
    socket.emit("wj_bet", { code: roomCode, username, amount: val });
}

function quickBet(amount) {
    document.getElementById("bet-input").value = amount;
    socket.emit("wj_bet", { code: roomCode, username, amount });
}

function doSwap() {
    socket.emit("wj_swap", { code: roomCode, username });
}
function doLock() { socket.emit("wj_lock", { code: roomCode, username }); }
function doHit() { socket.emit("wj_hit", { code: roomCode, username }); }
function doStand() { socket.emit("wj_stand", { code: roomCode, username }); }
function doDouble() { socket.emit("wj_double", { code: roomCode, username }); }
function newRound() { socket.emit("wj_new_round", { code: roomCode, username }); socket.emit("wj_lock", { code: roomCode, username });}

function renderDealerCards(hand, container) {
    container.innerHTML = "";
    (hand || []).forEach((c, i) => {
        const d = document.createElement("div");
        d.className = "bj-card";
        d.style.backgroundImage = cardImg(c);
        d.style.animationDelay  = (i * 0.12) + "s";
        container.appendChild(d);
    });
}

function renderYourHand(hand, container, swapPhase, swapsUsed) {
    container.innerHTML = "";
    (hand || []).forEach((c, i) => {
        const d = document.createElement("div");
        d.className = "bj-card";
        d.style.position = "relative";
        d.style.backgroundImage = cardImg(c);
        d.style.animationDelay  = (i * 0.12) + "s";
        if (swapPhase && i < 2) {
            if (swapsUsed < 1) {
                d.classList.add("swappable");
                d.onclick = () => doSwap();
            } else {
                d.classList.add("swap-used");
            }
        }
        container.appendChild(d);
    });
}

function render(data) {
    const phase      = data.phase;
    const myHand     = data.hands?.[username]  || [];
    const myStatus   = data.status?.[username];
    const myChips    = data.chips?.[username]  ?? 0;
    const myBet      = data.bets?.[username]   ?? 0;
    const myTurn     = data.turn === username;
    const mySwaps    = data.swaps_used?.[username] ?? 0;
    const results    = data.results || {};
    const myResult   = results[username];

    const dealerHand = (phase === "swap" || phase === "playing")
        ? (data.dealer_hand_visible || [])
        : (data.dealer_hand || []);
    renderDealerCards(dealerHand, document.getElementById("dealer-hand"));
    const dealerTotalEl = document.getElementById("dealer-total");
    if (phase === "done" || phase === "dealer") {
        const dt = data.dealer_total ?? baseTotal(data.dealer_hand || []);
        dealerTotalEl.textContent = `${dt}${data.dealer_busted ? " BUST" : ""}`;
    } else {
        const v = dealerHand[0] ? cardValue(dealerHand[0]) : "";
        dealerTotalEl.textContent = v !== "" ? `${v} + ?` : "";
    }

    const swapPhaseActive = phase === "swap" && myTurn && myStatus === "swapping";
    renderYourHand(myHand, document.getElementById("your-hand"), swapPhaseActive, mySwaps);

    const myTotal = (phase === "swap")
        ? baseTotal(myHand)
        : (data.running_total?.[username] ?? baseTotal(myHand));
    document.getElementById("your-total").textContent =
        myHand.length ? `${myTotal}${myTotal < 0 ? " BUST" : ""}` : "";

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
    const swapArea     = document.getElementById("swap-area");
    const playArea    = document.getElementById("play-area");
    const newRoundBtn = document.getElementById("new-round-btn");
    betArea.style.display     = "none";
    swapArea.style.display    = "none";
    playArea.style.display    = "none";
    newRoundBtn.style.display = "none";

    if (phase === "betting" && myStatus === "waiting") {
        betArea.style.display = "flex";
    } else if (swapPhaseActive) {
        swapArea.style.display = "flex";
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
            whitejack: `White Jack! +${myResult.winnings}`,
            win:  `✓ Win! +${myResult.winnings}`,
            push: `↔ Push`,
            lose: `✗ Lose`,
            bust: `✗ Bust`,
        };
        if (!banner.textContent) {
            banner.textContent = msgs[r] || "";
            banner.className   = `result-${r === "whitejack" ? "whitejack" : r} result-win-anim`;
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
            const labels = { win:"WIN", lose:"LOSE", push:"PUSH", bust:"BUST", whitejack:"WHITE JACK" };
            st.textContent = labels[r] || r.toUpperCase();
            zone.appendChild(st);
        } else if (pStatus && !["waiting", "bet_placed", "swapping"].includes(pStatus)) {
            const st = document.createElement("div");
            st.className = "opp-status";
            st.textContent = pStatus.replace("_"," ").toUpperCase();
            zone.appendChild(st);
        }

        oppContainer.appendChild(zone);
    });
}