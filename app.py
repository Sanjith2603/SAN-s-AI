from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for
)

from flask_sqlalchemy import SQLAlchemy

from flask_bcrypt import Bcrypt

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

from dotenv import load_dotenv

from openai import OpenAI

from pypdf import PdfReader

import os

# =========================
# LOAD ENV
# =========================

load_dotenv()

# =========================
# OPENROUTER
# =========================

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# =========================
# FLASK APP
# =========================

app = Flask(__name__)

app.config["SECRET_KEY"] = "supersecretkey"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["UPLOAD_FOLDER"] = "uploads"

db = SQLAlchemy(app)

bcrypt = Bcrypt(app)

login_manager = LoginManager(app)

login_manager.login_view = "login"

# =========================
# USER MODEL
# =========================

class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

# =========================
# CHAT MODEL
# =========================

class Chat(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    role = db.Column(
        db.String(20),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    file_type = db.Column(
        db.String(50),
        nullable=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

# =========================
# LOGIN MANAGER
# =========================

@login_manager.user_loader
def load_user(user_id):

    return User.query.get(int(user_id))

# =========================
# GLOBAL MEDIA CONTEXT
# =========================

media_context = ""

# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]

        email = request.form["email"]

        password = request.form["password"]

        hashed_password = bcrypt.generate_password_hash(
            password
        ).decode("utf-8")

        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)

        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]

        user = User.query.filter_by(
            email=email
        ).first()

        if user and bcrypt.check_password_hash(
            user.password,
            password
        ):

            login_user(user)

            return redirect(url_for("home"))

    return render_template("login.html")

# =========================
# LOGOUT
# =========================

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(url_for("login"))

# =========================
# CLEAR CHAT
# =========================

@app.route("/clear")
@login_required
def clear_chat():

    Chat.query.filter_by(
        user_id=current_user.id
    ).delete()

    db.session.commit()

    return redirect(url_for("home"))

# =========================
# MEDIA UPLOAD
# =========================

@app.route("/upload", methods=["POST"])
@login_required
def upload_file():

    global media_context

    file = request.files["file"]

    if not file:

        return redirect(url_for("home"))

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    file.save(filepath)

    # SAVE FILE MESSAGE IN CHAT

    upload_chat = Chat(

        role="assistant",

        message=f"📎 Uploaded file: {file.filename}",

        user_id=current_user.id,

        file_type="upload"
    )

    db.session.add(upload_chat)

    db.session.commit()

    filename = file.filename.lower()

    # PDF PROCESSING

    if filename.endswith(".pdf"):

        reader = PdfReader(filepath)

        text = ""

        for page in reader.pages:

            extracted = page.extract_text()

            if extracted:

                text += extracted

        media_context = text

    # IMAGE PROCESSING

    elif (
        filename.endswith(".png")
        or filename.endswith(".jpg")
        or filename.endswith(".jpeg")
    ):

        media_context = f"""
        User uploaded image:
        {file.filename}

        Analyze image if user asks about it.
        """

    # TEXT FILE PROCESSING

    elif filename.endswith(".txt"):

        with open(filepath, "r", encoding="utf-8") as f:

            media_context = f.read()

    else:

        media_context = f"""
        Uploaded file:
        {file.filename}
        """

    return redirect(url_for("home"))

# =========================
# HOME CHAT
# =========================

@app.route("/", methods=["GET", "POST"])
@login_required
def home():

    global media_context

    if request.method == "POST":

        user_message = request.form["message"]

        # SAVE USER MESSAGE

        user_chat = Chat(
            role="user",
            message=user_message,
            user_id=current_user.id
        )

        db.session.add(user_chat)

        db.session.commit()

        # LOAD CHAT HISTORY

        all_chats = Chat.query.filter_by(
            user_id=current_user.id
        ).all()

        messages = []

        # MEDIA CONTEXT

        if media_context:

            messages.append({
                "role":"system",
                "content":f"""
                Use this uploaded media context
                while answering:

                {media_context}
                """
            })

        # CHAT HISTORY

        for chat in all_chats:

            messages.append({
                "role": chat.role,
                "content": chat.message
            })

        # AI RESPONSE

        completion = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=messages
        )

        bot_response = completion.choices[0].message.content

        # SAVE AI RESPONSE

        bot_chat = Chat(
            role="assistant",
            message=bot_response,
            user_id=current_user.id
        )

        db.session.add(bot_chat)

        db.session.commit()

    # LOAD CHATS

    all_chats = Chat.query.filter_by(
        user_id=current_user.id
    ).all()

    chat_history = []

    for chat in all_chats:

        chat_history.append({
            "role": chat.role,
            "content": chat.message,
            "file_type": chat.file_type
        })

    return render_template(
        "index.html",
        chat_history=chat_history,
        username=current_user.username
    )

# =========================
# CREATE TABLES
# =========================

with app.app_context():

    db.create_all()

# =========================
# RUN APP
# =========================

if __name__ == "__main__":

    app.run(debug=True)