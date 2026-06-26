from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
import requests
import random
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "nigersaurus_skrivni_kljuc_123!"

DEEPSEEK_API_KEY = "sk-23064600e2a4423f94014d53302e833c" # Pazi na ključ!

# 24-urni časovnik (od 00:00 do 23:59)
URE_CASOVNIK = {i: f"{i:02d}:00 - {(i+1)%24:02d}:00" for i in range(24)}

# Funkcija za branje citatov iz datoteke citati.txt
def nalozi_citate():
    ZADRŽANI_CITATI = [
        {"quote": "Vrhunska umetnost vojne je podrediti si sovražnika brez boja.", "author": "Sun Tzu"},
        {"quote": "Sredi nereda se ponuja tudi priložnost.", "author": "Sun Tzu"},
        {"quote": "Uspeh je odvisen od predhodne priprave in brez nje bo zagotovo prišlo do neuspeha.", "author": "Sun Tzu"},
        {"quote": "Spoznaj sebe in spoznaj svojega nasprotnika, pa ne boš ogrožen v sto bitkah.", "author": "Sun Tzu"},
        {"quote": "Tisti, ki je previden in čaka na neprevidnega sovražnika, bo zmagal.", "author": "Sun Tzu"},
        {"quote": "Vsa vojna temelji na prevari. Ko smo sposobni napasti, se moramo zdeti nesposobni.", "author": "Sun Tzu"},
        {"quote": "Največja zmaga je tista, ki ne zahteva bitke.", "author": "Sun Tzu"}
    ]
    if not os.path.exists('citati.txt'):
        try:
            with open('citati.txt', 'w', encoding='utf-8') as f:
                for c in ZADRŽANI_CITATI:
                    f.write(f"{c['quote']}|{c['author']}\n")
            return ZADRŽANI_CITATI
        except:
            return ZADRŽANI_CITATI
    
    citati = []
    try:
        with open('citati.txt', 'r', encoding='utf-8') as f:
            for vrstica in f:
                if '|' in vrstica:
                    delov = vrstica.strip().split('|')
                    if len(delov) == 2:
                        citati.append({"quote": delov[0], "author": delov[1]})
        return citati if citati else ZADRŽANI_CITATI
    except:
        return ZADRŽANI_CITATI

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def inicializiraj_bazo():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS urnik (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, dan TEXT NOT NULL, ura INTEGER NOT NULL, kratica TEXT NOT NULL, profesor TEXT, ucilnica TEXT, FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS predmeti (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, ime TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS ocene (id INTEGER PRIMARY KEY AUTOINCREMENT, predmet_id INTEGER NOT NULL, vrednost INTEGER NOT NULL, komentar TEXT, FOREIGN KEY(predmet_id) REFERENCES predmeti(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, vloga TEXT NOT NULL, sporocilo TEXT NOT NULL, ustvarjeno DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

inicializiraj_bazo()

@app.route('/')
def domov():
    if 'user_id' not in session:
        return redirect(url_for('prijava'))
    citati = nalozi_citate()
    izbran = random.choice(citati)
    return render_template('domov.html', citat=izbran['quote'], avtor=izbran['author'])

@app.route('/prijava', methods=['GET', 'POST'])
def prijava():
    if request.method == 'POST':
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('domov'))
        flash('Napačno uporabniško ime ali geslo!', 'danger')
    return render_template('auth.html', način='prijava')

@app.route('/registracija', methods=['GET', 'POST'])
def registracija():
    if request.method == 'POST':
        hashed_password = generate_password_hash(request.form['password'])
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (request.form['username'], hashed_password))
            conn.commit()
            flash('Registracija uspešna!', 'success')
            return redirect(url_for('prijava'))
        except:
            flash('Ime že obstaja!', 'danger')
        finally:
            conn.close()
    return render_template('auth.html', način='registracija')

@app.route('/odjava')
def odjava():
    session.clear()
    return redirect(url_for('prijava'))

@app.route('/urnik', methods=['GET', 'POST'])
def urnik():
    if 'user_id' not in session: return redirect(url_for('prijava'))
    conn = get_db_connection()
    if request.method == 'POST':
        dan, ura, kratica, profesor, ucilnica = request.form['dan'], int(request.form['ura']), request.form['kratica'], request.form.get('profesor', ''), request.form.get('ucilnica', '')
        obstaja = conn.execute('SELECT id FROM urnik WHERE user_id = ? AND dan = ? AND ura = ?', (session['user_id'], dan, ura)).fetchone()
        if obstaja:
            conn.execute('UPDATE urnik SET kratica = ?, profesor = ?, ucilnica = ? WHERE id = ?', (kratica, profesor, ucilnica, obstaja['id']))
        else:
            conn.execute('INSERT INTO urnik (user_id, dan, ura, kratica, profesor, ucilnica) VALUES (?, ?, ?, ?, ?, ?)', (session['user_id'], dan, ura, kratica, profesor, ucilnica))
        conn.commit()
        return redirect(url_for('urnik'))
    
    urnik_podatki = conn.execute('SELECT * FROM urnik WHERE user_id = ?', (session['user_id'],)).fetchall()
    conn.close()
    
    urnik_grid = {u: {dan: None for dan in ['Ponedeljek', 'Torek', 'Sreda', 'Četrtek', 'Petek', 'Sobota', 'Nedelja']} for u in URE_CASOVNIK.keys()}
    for vnos in urnik_podatki:
        if vnos['ura'] in urnik_grid and vnos['dan'] in urnik_grid[vnos['ura']]:
            urnik_grid[vnos['ura']][vnos['dan']] = vnos
            
    return render_template('urnik.html', urnik_grid=urnik_grid, ure_casovnik=URE_CASOVNIK)

@app.route('/resetiraj-urnik', methods=['POST'])
def resetiraj_urnik():
    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute('DELETE FROM urnik WHERE user_id = ?', (session['user_id'],))
        conn.commit()
        conn.close()
    return redirect(url_for('urnik'))

@app.route('/izbrisi-urnik/<int:id>', methods=['POST'])
def izbrisi_urnik(id):
    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute('DELETE FROM urnik WHERE id = ? AND user_id = ?', (id, session['user_id']))
        conn.commit()
        conn.close()
    return redirect(url_for('urnik'))

@app.route('/predmeti', methods=['GET', 'POST'])
def predmeti():
    if 'user_id' not in session: return redirect(url_for('prijava'))
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('INSERT INTO predmeti (user_id, ime) VALUES (?, ?)', (session['user_id'], request.form['ime']))
        conn.commit()
        return redirect(url_for('predmeti'))
        
    predmeti_iz_baze = conn.execute('''
        SELECT p.*, 
               (SELECT AVG(o.vrednost) FROM ocene o WHERE o.predmet_id = p.id) as povprecje,
               (SELECT COUNT(*) FROM ocene o WHERE o.predmet_id = p.id AND o.vrednost = 5) as ima_petico
        FROM predmeti p WHERE p.user_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('predmeti.html', predmeti=predmeti_iz_baze)

@app.route('/izbrisi-predmet/<int:id>', methods=['POST'])
def izbrisi_predmet(id):
    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute('DELETE FROM ocene WHERE predmet_id = ?', (id,)) 
        conn.execute('DELETE FROM predmeti WHERE id = ? AND user_id = ?', (id, session['user_id']))
        conn.commit()
        conn.close()
    return redirect(url_for('predmeti'))

@app.route('/predmet/<int:predmet_id>', methods=['GET', 'POST'])
def predmet_detail(predmet_id):
    if 'user_id' not in session: return redirect(url_for('prijava'))
    conn = get_db_connection()
    predmet = conn.execute('SELECT * FROM predmeti WHERE id = ? AND user_id = ?', (predmet_id, session['user_id'])).fetchone()
    if not predmet: return redirect(url_for('predmeti'))
        
    if request.method == 'POST':
        conn.execute('INSERT INTO ocene (predmet_id, vrednost, komentar) VALUES (?, ?, ?)', (predmet_id, int(request.form['vrednost']), request.form.get('komentar', '')))
        conn.commit()
        return redirect(url_for('predmet_detail', predmet_id=predmet_id))
        
    ocene = conn.execute('SELECT * FROM ocene WHERE predmet_id = ?', (predmet_id,)).fetchall()
    povprecje = conn.execute('SELECT AVG(vrednost) as avg FROM ocene WHERE predmet_id = ?', (predmet_id,)).fetchone()['avg']
    conn.close()
    return render_template('predmet_detail.html', predmet=predmet, ocene=ocene, povprecje=povprecje)

@app.route('/izbrisi-oceno/<int:id>/<int:predmet_id>', methods=['POST'])
def izbrisi_oceno(id, predmet_id):
    if 'user_id' in session:
        conn = get_db_connection()
        conn.execute('DELETE FROM ocene WHERE id = ? AND predmet_id IN (SELECT id FROM predmeti WHERE user_id = ?)', (id, session['user_id']))
        conn.commit()
        conn.close()
    return redirect(url_for('predmet_detail', predmet_id=predmet_id))

@app.route('/ai-svetovalec')
def ai_svetovalec():
    if 'user_id' not in session: return redirect(url_for('prijava'))
    
    conn = get_db_connection()
    # Avtomatsko brisanje klepeta starejšega od 1 ure (-1 hour) namesto 1 tedna
    conn.execute("DELETE FROM chat_history WHERE user_id = ? AND ustvarjeno < datetime('now', '-1 hour')", (session['user_id'],))
    conn.commit()
    
    zgodovina = conn.execute("SELECT id, vloga, sporocilo FROM chat_history WHERE user_id = ? ORDER BY ustvarjeno ASC", (session['user_id'],)).fetchall()
    conn.close()
    
    return render_template('ai_svetovalec.html', zgodovina=zgodovina)

@app.route('/izbrisi-sporocilo/<int:id>', methods=['POST'])
def izbrisi_sporocilo(id):
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    conn = get_db_connection()
    conn.execute("DELETE FROM chat_history WHERE id = ? AND user_id = ?", (id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('ai_svetovalec'))

@app.route('/ai-vprasanje', methods=['POST'])
def ai_vprasanje():
    if 'user_id' not in session: return jsonify({"odgovor": "Seja potekla."}), 401
    uporabnikov_vnos = request.get_json().get('vprasanje', '')
    user_id = session['user_id']
    
    conn = get_db_connection()
    # Shranjevanje uporabnikovega vnosa v bazo
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (user_id, vloga, sporocilo) VALUES (?, 'user', ?)", (user_id, uporabnikov_vnos))
    user_msg_id = cursor.lastrowid
    conn.commit()
    
    predmeti = conn.execute('SELECT p.ime, (SELECT AVG(o.vrednost) FROM ocene o WHERE o.predmet_id = p.id) as povp FROM predmeti p WHERE p.user_id = ?', (user_id,)).fetchall()
    urnik_vsi = conn.execute('SELECT * FROM urnik WHERE user_id = ?', (user_id,)).fetchall()
    
    kontekst = "Uporabnik ima te predmete (ocene 5-10, 5 je NEGATIVNO!):\n"
    for p in predmeti:
        kontekst += f"- {p['ime']}: Povprečje {round(p['povp'],2) if p['povp'] else 'ni ocen'}\n"
        
    kontekst += "\nNjegov 24-urni urnik (študij, spanje, faks):\n"
    for u in urnik_vsi:
        kontekst += f"- {u['dan']} ob {u['ura']}:00: {u['kratica']} ({u['profesor']})\n"
        
    messages = [{"role": "system", "content": f"Si AI študijski asistent. Študent ima ta profil:\n{kontekst}\nSvetuj mu kdaj naj spi, jé in se uči na podlagi urnika. Odgovori kratko, v slovenščini, pazi na negativne ocene (5). Uporabljaj običajen tekst, za poudarke pa lahko uporabiš **krepko** ali _podčrtano_."}]
    
    # Pridobivanje zadnjih 4 sporočil iz baze za kontekst (brez trenutno vstavljenega vnosa)
    zadnji_klepeti = conn.execute("SELECT vloga, sporocilo FROM chat_history WHERE user_id = ? AND id < ? ORDER BY ustvarjeno DESC LIMIT 4", (user_id, user_msg_id)).fetchall()
    zadnji_klepeti.reverse()
    
    for chat in zadnji_klepeti:
        messages.append({"role": "assistant" if chat['vloga'] == "ai" else "user", "content": chat['sporocilo']})
    messages.append({"role": "user", "content": uporabnikov_vnos})
    
    try:
        res = requests.post("https://api.deepseek.com/chat/completions", json={"model": "deepseek-chat", "messages": messages}, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"})
        odgovor_ai = res.json()['choices'][0]['message']['content'] if res.status_code == 200 else "Napaka API-ja."
    except Exception as e:
        odgovor_ai = f"Napaka: {str(e)}"
        
    # Shranjevanje AI odgovora v bazo
    cursor.execute("INSERT INTO chat_history (user_id, vloga, sporocilo) VALUES (?, 'ai', ?)", (user_id, odgovor_ai))
    ai_msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({"odgovor": odgovor_ai, "user_id": user_msg_id, "ai_id": ai_msg_id})

if __name__ == '__main__':
    app.run(debug=True)