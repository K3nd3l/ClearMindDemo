from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
import os
import openai
from datetime import datetime
import calendar
import hashlib

app = Flask(__name__)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
AUDIO_FOLDER = os.path.join(APP_ROOT, 'audio')

ai_key = None

if not os.path.exists('accounts'):
    os.makedirs('accounts')

def load_ai_key():
    global ai_key
    if ai_key is None:
        key_file_path = os.path.join(os.path.dirname(__file__), 'AI_Key', 'key.txt')
        print(f"Looking for AI key at: {key_file_path}")
        try:
            with open(key_file_path, 'r') as file:
                ai_key = file.read().strip()
                print(f"Loaded AI key: {ai_key[:5]}...")
        except Exception as e:
            print(f"Error reading AI key file: {e}")

load_ai_key()

if ai_key:
    openai.api_key = ai_key
else:
    print("AI key not found or could not be loaded.")


@app.route("/notes")
def notes():
    now = datetime.now()
    year = request.args.get('year', now.year, type=int)
    month = request.args.get('month', now.month, type=int)
    
    action = request.args.get('action')
    if action == 'prev':
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1
    elif action == 'next':
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1

    cal = calendar.Calendar(firstweekday=6)  # Sunday as the first day of the week
    days_with_notes = set()
    for filename in os.listdir(AUDIO_FOLDER):
        if filename.endswith('_transcription.txt'):
            try:
                date_str = filename.split('_')[0]
                date = datetime.strptime(date_str, '%Y-%m-%d')
                if date.year == year and date.month == month:
                    days_with_notes.add(date.day)
            except ValueError:
                continue

    month_days = cal.monthdayscalendar(year, month)
    month_calendar = '<table class="calendar-table">'
    month_calendar += '<thead><tr><th>S</th><th>M</th><th>T</th><th>W</th><th>T</th><th>F</th><th>S</th></tr></thead>'
    month_calendar += '<tbody>'

    for week in month_days:
        month_calendar += '<tr>'
        for day in week:
            if day == 0:
                month_calendar += '<td></td>'
            else:
                day_str = f'{year}-{month:02d}-{day:02d}'
                highlight_class = 'highlight' if day in days_with_notes else ''
                month_calendar += (f'<td class="{highlight_class}">'
                                   f'<a href="?year={year}&month={month}&day={day}">{day}</a></td>')
        month_calendar += '</tr>'

    month_calendar += '</tbody></table>'

    current_month_name = calendar.month_name[month]
    current_year = year
    
    selected_day = request.args.get('day')
    notes_contents = []
    if selected_day:
        selected_day_formatted = f"{year}-{month:02d}-{int(selected_day):02d}"
        print(f"Looking for notes on: {selected_day_formatted}")
        for filename in os.listdir(AUDIO_FOLDER):
            if filename.startswith(f"{selected_day_formatted}_") and filename.endswith('_transcription.txt'):
                file_path = os.path.join(AUDIO_FOLDER, filename)
                print(f"Found file: {file_path}")
                try:
                    with open(file_path, 'r') as file:
                        notes_contents.append(file.read())
                        print(f"Notes content from file: {file.read()}")
                except Exception as e:
                    print(f"Error reading file: {e}")

    return render_template('notes.html', 
                           title='Notes', 
                           calendar=month_calendar, 
                           current_month_name=current_month_name, 
                           current_year=current_year, 
                           current_month=month, 
                           selected_day=selected_day, 
                           notes_contents=notes_contents)


@app.route('/view_note/<filename>')
def view_note(filename):
    try:
        return send_from_directory(AUDIO_FOLDER, filename)
    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route("/userProfile")
def userProfile():
    username = 'default_user'
    return render_template('userProfile.html', title='User Profile', username=username)


@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/home")
def home():
    return render_template('home.html', title='Home')


@app.route("/transcribe", methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    # Save the uploaded audio file with a date in the filename
    audio_file = request.files['audio']
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d_%H-%M-%S")
    audio_filename = f"{date_str}_audio.wav"
    audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    audio_file.save(audio_path)

    # Use OpenAI Whisper API to transcribe the audio
    try:
        with open(audio_path, "rb") as f:
            response = openai.Audio.transcribe(model="whisper-1", file=f)

        transcription = response['text']

        # Save transcription to a .txt file
        transcription_filename = f"{date_str}_transcription.txt"
        transcription_path = os.path.join(AUDIO_FOLDER, transcription_filename)
        with open(transcription_path, "w") as txt_file:
            txt_file.write(transcription)

        return jsonify({"transcription": transcription})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    if username == 'admin' and password == 'password':
        return redirect(url_for('home'))

    account_file_path = os.path.join('accounts', f'{username}.txt')
    if not os.path.exists(account_file_path):
        flash('Invalid username or password')
        return redirect(url_for('login_page'))

    # Read the stored hashed password from the account file
    with open(account_file_path, 'r') as file:
        lines = file.readlines()
        stored_password = [line.split(": ")[1].strip() for line in lines if line.startswith("Password")][0]

    hashed_input_password = hashlib.sha256(password.encode()).hexdigest()

    if stored_password == hashed_input_password:
        return redirect(url_for('home'))
    else:
        flash('Invalid username or password')
        return redirect(url_for('login_page'))

    

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
   
        account_file_path = os.path.join('accounts', f'{username}.txt')
        if os.path.exists(account_file_path):
            return jsonify({"success": False, "message": "Username already exists."})

   
        with open(account_file_path, 'w') as file:
            file.write(f"Username: {username}\n")
            file.write(f"Email: {email}\n")
            file.write(f"Password: {password}\n")

        return jsonify({"success": True})


    return render_template('register.html')


@app.route('/')
def login_page():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)
