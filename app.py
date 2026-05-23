from flask import Flask, render_template, request, redirect, session, send_file
import random
import time

from pymongo import MongoClient


from flask_mail import Mail, Message
import markdown

#======= for Resume Pdf =======
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# ================= GROQ =================
from openai import OpenAI

# ================= EXTRA =================
import os
import requests
from dotenv import load_dotenv

# ================= LOAD ENV =================
load_dotenv()

app = Flask(__name__)
app.secret_key = "secret123"

# ================= GEMINI AI =================

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# ================= JOB API =================

JOB_API_KEY = os.getenv("JOB_API_KEY")

# ================= DATABASE =================
mongo_client = MongoClient(os.getenv("MONGO_URI"))

db = mongo_client["jobfinder"]
users = db["users"]


# ================= CREATE TABLE =================



# ================= MAIL =================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

mail = Mail(app)

# ================= OTP STORAGE =================

otp_store = {}

# ================= OTP GENERATE =================

def generate_otp():
    return random.randint(100000, 999999)


# ================= SEND OTP =================

def send_otp(email, otp):

    msg = Message(
        subject="🔐 Job Finder - OTP Verification",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.html = f"""
    <div style="font-family:Arial; background:#0f172a; padding:20px; border-radius:10px; color:white;">

        <h2 style="color:#38bdf8;">🔐 OTP Verification</h2>

        <p>Hello User,</p>

        <p>Your One Time Password (OTP) for <b>Job Finder</b> login/signup is:</p>

        <div style="font-size:22px; font-weight:bold; color:#00ffd5; margin:15px 0;">
            {otp}
        </div>

        <p>This OTP is valid for a short time. Do not share it with anyone.</p>

        <hr style="border:0; border-top:1px solid #334155; margin:20px 0;">

        <p style="font-size:14px; color:#94a3b8;">
            🚀 Powered by <b>Job Finder AI System</b>
        </p>

        <p style="font-size:14px; color:#94a3b8;">
            👨‍💻 Created by <b>Pawan Kumar Shrivastav</b>
        </p>

        <p style="font-size:13px; color:#64748b;">
            Regards,<br>
            Nawal Pawan Team
        </p>

    </div>
    """

    mail.send(msg)

# ================= HOME =================

@app.route('/')
def home():

    if 'user' not in session:

        return redirect('/login')

    return render_template("index.html")

# ================= JOB SEARCH =================

@app.route('/jobs')
def jobs():

    job = request.args.get("job", "")
    location = request.args.get("location", "")
    page = request.args.get("page", 1)

    query = f"{job} {location}".strip()

    url = "https://jsearch.p.rapidapi.com/search"

    headers = {
        "X-RapidAPI-Key": JOB_API_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    params = {
        "query": query,
        "page": page,
        "num_pages": 1,
        "country": "in"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params
        )

        data = response.json()

        return render_template(
            "index.html",
            jobs=data.get("data", []),
            job=job,
            location=location,
            page=int(page),
            is_search=True
        )

    except Exception as e:

        return f"Error : {str(e)}"

# ================= SIGNUP =================

@app.route('/signup', methods=['GET', 'POST'])
def signup():

    if request.method == 'POST':

        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not name or not email or not password:

            return "All fields required"

        otp = generate_otp()

        otp_store[email] = {
            "otp": otp,
            "name": name,
            "password": password,
            "type": "signup"
        }

        send_otp(email, otp)

        return render_template(
            "verify.html",
            email=email
        )

    return render_template("signup.html")

# ================= LOGIN =================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        user = users.find_one({
    "email": email,
    "password": password
})

        if user:

            session['user'] = email

            return redirect('/')

        else:

            return "Wrong email or password"

    return render_template("login.html")

# ================= FORGOT PASSWORD =================

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():

    if request.method == 'POST':

        email = request.form.get('email')

        if not email:

            return "Email required"

        otp = generate_otp()

        otp_store[email] = {
            "otp": otp,
            "time": time.time(),
            "type": "forgot"
        }

        send_otp(email, otp)

        return render_template(
            "verify.html",
            email=email
        )

    return render_template("forgot.html")

# ================= VERIFY OTP =================

@app.route('/verify', methods=['GET', 'POST'])
def verify():

    email = request.form.get('email')
    otp = request.form.get('otp')

    if not email or not otp:

        return "Missing email or OTP"

    data = otp_store.get(email)

    if not data:

        return "OTP not found"

    if str(data['otp']) != otp:

        return "Wrong OTP"

    # ================= SIGNUP VERIFY =================

    if data['type'] == "signup":

       users.insert_one({
    "name": data['name'],
    "email": email,
    "password": data['password'],
    "bio": "",
    "image": ""
})

        return redirect('/login')

    # ================= FORGOT VERIFY =================

    if data['type'] == "forgot":

        if time.time() - data["time"] > 60:

            return "OTP expired"

        session['reset_email'] = email

        return render_template("reset.html")

# ================= RESEND OTP =================

@app.route('/resend', methods=['POST'])
def resend():

    email = request.form.get('email')

    if not email:

        return "Email missing"

    old_data = otp_store.get(email)

    if not old_data:

        return "Session expired"

    otp = generate_otp()

    otp_store[email] = {
        "otp": otp,
        "type": old_data.get("type"),
        "name": old_data.get("name"),
        "password": old_data.get("password"),
        "time": time.time()
    }

    send_otp(email, otp)

    return render_template(
        "verify.html",
        email=email
    )

# ================= RESET PASSWORD =================

@app.route('/reset', methods=['POST'])
def reset():

    email = session.get("reset_email")
    password = request.form.get('password')

    if not email or not password:

        return "Error"

    users.update_one(
    {"email": email},
    {"$set": {
        "password": password
    }}
)

    return redirect('/login')

# ================= CHATBOT =================

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():

    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == 'POST':

        user_message = request.form.get("message")

        if user_message:

            try:

                messages = [

{
    "role": "system",
    "content": """
You are an advanced AI assistant for a Job Finder website.

ABOUT THE CREATOR:
- This website is created by Pawan Kumar Shrivastav.
- He is a B.Tech Computer Science student at Shobhit University, Meerut.
- He is from Bihar, India.
- He is a passionate web developer and AI learner.
- He builds projects like job finder websites, chatbots, resume analyzer, and AI tools.

RULES:
- Always give clean, structured answers.
- Use headings, bullet points, and spacing.
- Remember conversation context.
- Be friendly and professional.

LANGUAGE RULE:
- If user asks in English → reply in English.
- If user asks in Hindi → reply in simple Hindi.
- Match user language automatically.

CONTACT RULE:
- If user asks for phone number:
  DO NOT give phone number directly.
  Instead provide WhatsApp link:

 <a href="https://wa.me/919798430679" class="wa-btn" target="_blank">Chat on WhatsApp</a>

- If user asks WhatsApp:
  Always give clickable link.

CREATOR QUESTION RULE:
- If someone asks who created you:
  Say:
  "This chatbot and website was created by Pawan Kumar Shrivastav."

HELP AREAS:
- Jobs and career guidance
- Resume building and analysis
- Coding help (Python, C, HTML, CSS, JS)
- Interview preparation
- Project guidance

Be smart, helpful, and context aware like a professional AI assistant.

Help users with:
- Jobs
- Resume
- Coding
- Career guidance
- Interview questions
- General questions

Be friendly and professional.
"""
}
                ]

                for chat in session["chat_history"]:

                    messages.append({
                        "role": "user",
                        "content": chat["user"]
                    })

                    messages.append({
                        "role": "assistant",
                        "content": chat["bot"]
                    })

                messages.append({
                    "role": "user",
                    "content": user_message
                })

                response = client.chat.completions.create(

                    model="llama-3.3-70b-versatile",

                    messages=messages,

                    temperature=0.7
                )

                reply = response.choices[0].message.content

            except Exception as e:

                reply = f"Error: {str(e)}"

            session["chat_history"].append({

                "user": user_message,
                "bot": reply
            })

            session.modified = True

    return render_template(

        "chatbot.html",

        chat_history=session["chat_history"]
    )

@app.route('/clear-chat', methods=['POST'])
def clear_chat():

    session.pop("chat_history", None)

    return redirect('/chatbot')

# ================= LOGOUT =================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login')

# =============Pdf Resume=========

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/resume", methods=["GET", "POST"])
def resume():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        city = request.form.get("city")

        summary = request.form.get("summary")
        skills = request.form.get("skills")
        education = request.form.get("education")
        projects = request.form.get("projects")
        experience = request.form.get("experience")
        hobbies = request.form.get("hobbies")

        pdf_path = "static/resume.pdf"

        c = canvas.Canvas(pdf_path, pagesize=letter)

        y = 750

        c.setFont("Helvetica-Bold", 20)
        c.drawString(200, y, name)

        y -= 40

        c.setFont("Helvetica", 12)

        lines = [

            f"Email: {email}",
            f"Phone: {phone}",
            f"City: {city}",
            "",
            f"Summary: {summary}",
            "",
            f"Skills: {skills}",
            "",
            f"Education: {education}",
            "",
            f"Projects: {projects}",
            "",
            f"Experience: {experience}",
            "",
            f"Hobbies: {hobbies}"

        ]

        for line in lines:

            c.drawString(50, y, line)

            y -= 20

        c.save()

        return send_file(pdf_path, as_attachment=True)

    return render_template("resume.html")
# ---------profile-------------

@app.route('/profile', methods=['GET', 'POST'])
def profile():

    if 'user' not in session:
        return redirect('/login')

    email = session['user']

    row = users.find_one({"email": email})

    if request.method == 'POST':

        bio = request.form.get('bio')
        new_email = request.form.get('email')
        file = request.files.get('image')

        image_name = row.get("image", "default.png") if row else "default.png"

        if file and file.filename != "":
            image_name = file.filename
            file.save("static/uploads/" + image_name)

        users.update_one(
            {"email": email},
            {"$set": {
                "email": new_email,
                "bio": bio,
                "image": image_name
            }}
        )

        session['user'] = new_email

        return redirect('/profile')

    user = {
        "username": row.get("name") if row else "",
        "email": row.get("email") if row else "",
        "bio": row.get("bio", "") if row else "",
        "image": row.get("image", "default.png") if row else "default.png"
    }

    return render_template("profile.html", user=user)
# ------------Resume Analyzer-----------

@app.route('/resume-analyzer', methods=['GET', 'POST'])
def resume_analyzer():

    result = ""

    if request.method == 'POST':

        file = request.files.get("resume_pdf")

        resume_text = ""

        if file:

            reader = PdfReader(file)

            for page in reader.pages:
                resume_text += page.extract_text() or ""

        if resume_text.strip() == "":
            return "No text found in PDF"

        response = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[

                {
                    "role": "system",
                    "content": "You are a professional ATS Resume Analyzer."
                },

                {
                    "role": "user",
                    "content": resume_text
                }

            ]
            
        )

        result = response.choices[0].message.content

    return render_template("resume_analyzer.html", result=result)

# ================= RUN =================



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
