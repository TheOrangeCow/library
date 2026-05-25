const PROFANITY_LIST = ["badword1", "badword2", "damn", "hell", "crap", "idiot", "stupid"];

function containsProfanity(msg) {
    return PROFANITY_LIST.some(w => {
        const re = new RegExp(`\\b${w}\\b`, "i");
        return re.test(msg);
    });
}

function buildMessage(text, fromSelf, sender) {
    const hasProfanity = containsProfanity(text);
    const wrap = document.createElement("div");
    wrap.className = "msg-global";

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const textNode = document.createElement("span");
    if (fromSelf){
        textNode.textContent = `<strong>You:</strong> ${text}`
    }else{
        textNode.textContent = `<strong>${sender}:</strong> ${text}`;
    }

    if (hasProfanity) {
        let revealed = false;
        textNode.style.filter = "blur(4px)";
        textNode.style.transition = "filter 0.25s ease";
        textNode.style.display = "inline-block";

        bubble.appendChild(textNode);
        bubble.appendChild(badge);
        bubble.style.cursor = "pointer";

        bubble.addEventListener("click", () => {
            revealed = !revealed;
            textNode.style.filter = revealed ? "none" : "blur(4px)";
        });
    } else {
        bubble.appendChild(textNode);
    }

    wrap.appendChild(bubble);
    return wrap;
}