# from flask import Flask
from app import app
from app.bot import amanda
from app.models import ChatRequest, Conversation, Message, Members
from app import queries
from flask import request, render_template, session, redirect
from uuid import uuid4
from app.forms import QuoteForm

from app.database import PgSession
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.models import Conversation, Message, RoomCombinations, RoomTypes, RoomRates, Allotments, Calendar, Contracts
@app.route("/reservation", methods=["GET", "POST"])
def chat():
    # one conversation per browser, kept in Flask's session cookie (no JS needed)
    if "conversation_id" not in session:
        session["conversation_id"] = str(uuid4())
    conversation_id = session["conversation_id"]

    if not queries.conversation_exists(conversation_id):
        queries.create_conversation(conversation_id)

    if request.method == "POST":
        message = request.form.get("message", "").strip()  # <-- form field, not JSON
        if message:
            queries.save_message(conversation_id, "user", message)
            history = queries.load_history(conversation_id)
            result = amanda.generate_response(history, max_tokens=1000)
            queries.save_message(conversation_id, "assistant", result)

    history = queries.load_history(conversation_id)
    return render_template("chat.html", history=history)


@app.route("/reservation/clear", methods=["POST"])
def borrar_chat():
    session.pop("conversation_id", None)
    return redirect("/app/reservation")

@app.route("/pay")
def pay():
    return render_template('pay.html')

@app.route("/quote", methods=['GET', 'POST'])
def quote():
    #create an instance of QuoteForm
    Quote_Form = QuoteForm()
    return render_template('quote.html', quote=Quote_Form)


@app.route("/members", methods=['GET', 'POST'])
def members():
    with PgSession() as session:
        query = select(Contracts.contract_number, Contracts.is_active,
        Contracts.contract_date, Contracts.contract_term_years, Contracts.contract_price,)
        rows = session.execute(query).all()
        return render_template("members.html", rows=rows)
