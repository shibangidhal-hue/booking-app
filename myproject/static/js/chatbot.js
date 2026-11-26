document.addEventListener("DOMContentLoaded", function () {
    const toggleButton = document.getElementById("chatbot-toggle");
    const chatbotWindow = document.getElementById("chatbot-window");
    const closeButton = document.getElementById("chatbot-close");
    const chatForm = document.getElementById("chatbot-form");
    const messageInput = document.getElementById("chatbot-message");
    const messagesContainer = document.getElementById("chatbot-messages");

    // Stop safely if chatbot HTML has not been added yet.
    if (!toggleButton || !chatbotWindow || !chatForm ||
        !messageInput || !messagesContainer) {
        return;
    }

    toggleButton.addEventListener("click", function () {
        chatbotWindow.style.display = "block";
        messageInput.focus();
    });

    if (closeButton) {
        closeButton.addEventListener("click", function () {
            chatbotWindow.style.display = "none";
        });
    }

    function getCookie(name) {
        const match = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
        return match ? decodeURIComponent(match[2]) : "";
    }

    function addMessage(text, sender) {
        const message = document.createElement("div");
        message.classList.add("chat-message", sender);
        message.textContent = text;
        messagesContainer.appendChild(message);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return message;
    }

    chatForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const message = messageInput.value.trim();

        if (!message) return;

        addMessage(message, "user-message");
        messageInput.value = "";
        messageInput.disabled = true;

        const loadingMessage = addMessage("Thinking...", "bot-message");

        const sendButton = chatForm.querySelector("button");
        if (sendButton) sendButton.disabled = true;

        try {
            const response = await fetch("/api/chatbot/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken")
                },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();
            loadingMessage.remove();

            if (!response.ok) {
                throw new Error(data.reply || "Unable to get a response.");
            }

            addMessage(data.reply || "Sorry, I couldn't generate a reply.", "bot-message");

        } catch (error) {
            addMessage(
                error.message || "Unable to connect to the AI assistant.",
                "bot-message"
            );
        } finally {
            messageInput.disabled = false;
            if (sendButton) sendButton.disabled = false;
            messageInput.focus();
        }
    });
});