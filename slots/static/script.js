const SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣", "🃏"];

function changeBet(delta) {
    const input = document.getElementById("bet-input");
    const max = parseInt(input.max) || 99999;
    let val = parseInt(input.value) || 1;
    val = Math.max(1, Math.min(max, val + delta));
    input.value = val;
}

function randomSymbol() {
    return SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)];
}

async function startSpin() {
    const btn = document.getElementById("spin-btn");
    const bet = document.getElementById("bet-input").value;
    btn.disabled = true;
    document.getElementById("win-line").classList.remove("active");

    const reelEls = [0, 1, 2].map(i => document.querySelector(`#reel-${i} .reel-symbol`));

    reelEls.forEach(r => {
        r.classList.remove("landed");
        r.classList.add("spinning");
    });

    const intervals = reelEls.map(r =>
        setInterval(() => { r.textContent = randomSymbol(); }, 80)
    );

    const form = document.getElementById("spin-form");
    const data = new FormData(form);
    const resp = await fetch("/slots/spin", { method: "POST", body: data });
    const result = await resp.json();

    if (result.error) {
        intervals.forEach(clearInterval);
        reelEls.forEach(r => r.classList.remove("spinning"));
        document.getElementById("result-display").innerHTML =
            `<div class="result-lose">${result.error}</div>`;
        btn.disabled = false;
        return;
    }

    reelEls.forEach((r, i) => {
        setTimeout(() => {
            clearInterval(intervals[i]);
            r.textContent = result.reels[i];
            r.classList.remove("spinning");
            r.classList.add("landed");
        }, 400 + i * 300);
    });

    const allLanded = 400 + 2 * 300 + 200;
    setTimeout(() => {
        if (result.result !== "lose") {
            document.getElementById("win-line").classList.add("active");
        }
        const display = document.getElementById("result-display");

        if (display) {
            if (result.result === "jackpot") {
                display.innerHTML = `<div class="result-jackpot">JACKPOT! +${result.winnings} chips!</div>`;
            } else if (result.result === "win") {
                display.innerHTML = `<div class="result-win">✓ Win! +${result.winnings} chips</div>`;
            } else {
                display.innerHTML = `<div class="result-lose">✗ No win</div>`;
            }
        }

        document.getElementById("chips-display").textContent = `${result.chips} chips`;

        btn.disabled = false;
    }, allLanded);
}