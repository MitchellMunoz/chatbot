from flask import Flask
from app import app
from app.bot import amanda
from app.models import ChatRequest, Conversation, Message
from app import queries
from flask import request, render_template, session
from uuid import uuid4


@app.route("/chat", methods=["GET", "POST"])
def chat():
    # one conversation per browser, kept in Flask's session cookie (no JS needed)
    if "conversation_id" not in session:
        session["conversation_id"] = str(uuid4())
    conversation_id = session["conversation_id"]

    if not queries.conversation_exists(conversation_id):
        queries.create_conversation(conversation_id)

    if request.method == "POST":
        message = request.form["message"]              # <-- form field, not JSON
        queries.save_message(conversation_id, "user", message)
        history = queries.load_history(conversation_id)
        result = amanda.generate_response(history, max_tokens=1000)
        queries.save_message(conversation_id, "assistant", result)

    history = queries.load_history(conversation_id)
    return render_template("chat.html", history=history)