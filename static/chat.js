function normalize(msg) {
    return msg
        .toLowerCase()
        .replace(/[^a-z0-9]/g, "")
        .replace(/1/g, "i")
        .replace(/3/g, "e")
        .replace(/4/g, "a")
        .replace(/0/g, "o")
        .replace(/5/g, "s");
}

function badword(msg) {
    const clean = normalize(msg);
    return badword_list.some(w => new RegExp(`\\b${w}\\b`).test(clean));
}

function buildMessage(text, fromSelf, sender) {
    const hasProfanity = badword(text);
    const wrap = document.createElement("div");
    wrap.className = "msg-global";

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const textNode = document.createElement("span");
    if (fromSelf){
        textNode.innerHTML = `<strong>You:</strong> ${text}`
    }else{
        textNode.innerHTML = `<strong>${sender}:</strong> ${text}`;
    }

    if (hasProfanity) {
        let revealed = false;
        textNode.style.filter = "blur(4px)";
        textNode.style.transition = "filter 0.25s ease";
        textNode.style.display = "inline-block";

        bubble.appendChild(textNode);
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

function resetChat() {
    document.getElementById("chat-messages").innerHTML = "";
}

function sendMessage() {
    const input = document.getElementById("chat-input");
    const msg = input.value.trim();
    if (!msg) return;
    socket.emit(chatsendid, { msg, code: roomCode });
    input.value = "";
}

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

document.getElementById("chat-send").onclick = sendMessage;
document.getElementById("chat-input").onkeydown = e => { if (e.key === "Enter") sendMessage(); };

document.addEventListener("visibilitychange", () => {
    socket.emit(document.visibilityState === "hidden" ? "tab_hidden" : "tab_visible");
});

socket.on(chatreceiveid, (data) => {
    const msgDiv = document.getElementById("chat-messages");
    msgDiv.appendChild(buildMessage(data.msg, data.sender === username, data.sender));
    msgDiv.scrollTop = msgDiv.scrollHeight;
});

socket.on('update_user_list', function(users) {
    const listElement = document.getElementById('user-list');
    listElement.innerHTML = '';
    users
        .filter(u => u.name !== username && u.page === `Gaming:${roomCode}`)
        .forEach(user => {
            const li = document.createElement('li');
            const dotClass = user.status === "Active" ? "dot-active" : "dot-away";
            li.innerHTML = `<span class="status-dot ${dotClass}"></span>${user.name}`;
            listElement.appendChild(li);
        });
});