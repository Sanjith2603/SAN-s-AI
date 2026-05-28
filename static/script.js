const chatBox = document.getElementById("chat-box");

chatBox.scrollTop = chatBox.scrollHeight;

const form = document.getElementById("chat-form");

form.addEventListener("submit", () => {

    const typingDiv = document.createElement("div");

    typingDiv.classList.add("message-wrapper");
    typingDiv.classList.add("assistant");

    typingDiv.innerHTML = `
    
        <div class="message assistant">
            AI is thinking...
        </div>
    
    `;

    chatBox.appendChild(typingDiv);

    chatBox.scrollTop = chatBox.scrollHeight;
});