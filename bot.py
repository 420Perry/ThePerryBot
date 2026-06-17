from telegram.ext import Application, CommandHandler
from datetime import datetime
import sqlite3
import re
import dateparser
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import sqlite3
import requests #x meteo
import os
import sqlite3

def init_db():

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    # 💰 TABELLA SPESE
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            description TEXT
        )
    """)

    # 📅 TABELLA PROMEMORIA
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            event_time TEXT
        )
    """)

    conn.commit()
    conn.close()
TOKEN = os.getenv("TOKEN")

scheduler = BackgroundScheduler()

def load_reminders_from_db():

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, text, event_time
        FROM reminders
    """)

    dati = cur.fetchall()
    conn.close()

    for user_id, text, event_time in dati:

        try:
            schedule_reminder(user_id, text, event_time)
        except:
            pass


async def start(update, context):
    await update.message.reply_text(
        "Bot avviato correttamente!"
    )

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))


async def spesa(update, context):  #spesa

    testo = " ".join(context.args)

    match = re.match(r"(\d+[.,]?\d*)\s*€?\s*(.*)", testo)

    if not match:
        await update.message.reply_text(
            "Formato: /spesa 15 ristorante"
        )
        return

    importo = float(
        match.group(1).replace(",", ".")
    )

    descrizione = match.group(2)

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO expenses
        (user_id, amount, description)
        VALUES (?, ?, ?)
        """,
        (
            update.effective_user.id,
            importo,
            descrizione
        )
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Nuova spesa:\n{importo:.2f}€ {descrizione}"
    )

app.add_handler(CommandHandler("spesa", spesa))


async def spese(update, context):   #spese

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, amount, description
        FROM expenses
        WHERE user_id=?
        """,
        (update.effective_user.id,)
    )

    righe = cur.fetchall()

    conn.close()

    if not righe:
        await update.message.reply_text(
            "Nessuna spesa registrata."
        )
        return

    totale = 0
    testo = ""

    for riga in righe:

        totale += riga[1]

        testo += (
            f"{riga[0]}. "
            f"{riga[1]:.2f}€ "
            f"{riga[2]}\n"
        )

    testo += f"\nTotale: {totale:.2f}€"

    await update.message.reply_text(testo)

app.add_handler(CommandHandler("spese", spese))


async def eliminaspesa(update, context): #elimina spese

    if not context.args:
        return

    id_spesa = context.args[0]

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM expenses
        WHERE id=?
        AND user_id=?
        """,
        (
            id_spesa,
            update.effective_user.id
        )
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "🗑️ Spesa eliminata."
    )

app.add_handler(
    CommandHandler(
        "eliminaspesa",
        eliminaspesa
    )
)


async def help_command(update, context): #help command

    testo = """
📖 COMANDI DISPONIBILI

💰 SPESA
/spesa 12 Spotify
Aggiunge una spesa

/spese
Mostra tutte le spese

/eliminaspesa ID
Elimina una spesa


📅 PROMEMORIA
/fare 17 settembre 9:30 dentista
Aggiunge un promemoria

/promemoria
Mostra tutti i promemoria

/eliminapromemoria ID
Elimina un promemoria


☀️ METEO
/meteo
Mostra il meteo di oggi a Ivrea

🌤 Automazione:
Ogni mattina alle 07:30 ricevi automaticamente il meteo di Ivrea


❓ AIUTO
/help
Mostra questo messaggio
"""

    await update.message.reply_text(testo)

app.add_handler(CommandHandler("help", help_command))


async def send_message(user_id, text):  #notifiche promemoria
    await app.bot.send_message(chat_id=user_id, text=text)

def schedule_reminder(user_id, text, event_time):

    dt = datetime.fromisoformat(event_time)

    # 🌙 giorno prima alle 21:30
    day_before = dt - timedelta(days=1)
    day_before = day_before.replace(hour=21, minute=30)

    # 🌅 mattina stesso giorno alle 07:30
    morning = dt.replace(hour=7, minute=30)

    # ⏰ 2 ore prima
    two_hours_before = dt - timedelta(hours=2)

    jobs = [
        (day_before, f"🌙 Domani: {text}"),
        (morning, f"🌅 Oggi: {text}"),
        (two_hours_before, f"⏰ Tra 2 ore: {text}")
    ]

    for run_time, message in jobs:

        if run_time > datetime.now():

            scheduler.add_job(
                send_message,
                "date",
                run_date=run_time,
                args=[user_id, message]
            )


async def fare(update, context):  #scrivere promemoria (/fare)

    import sqlite3
    from datetime import datetime
    import re

    testo = " ".join(context.args).lower()

    if not testo:
        await update.message.reply_text(
            "Uso:\n/fare 17 settembre 9:30 palestra"
        )
        return

    # 🔥 1. estrai data + ora (robusto)
    match = re.search(
        r"(\d{1,2})\s*([a-zà]+)\s*(\d{1,2}[:.,]\d{2}|\d{1,2})",
        testo
    )

    if not match:
        await update.message.reply_text(
            "❌ Formato non riconosciuto"
        )
        return

    giorno = int(match.group(1))
    mese_nome = match.group(2)
    ora_raw = match.group(3)

    # 🔥 2. mesi italiani
    mesi = {
        "gennaio":1, "febbraio":2, "marzo":3, "aprile":4,
        "maggio":5, "giugno":6, "luglio":7, "agosto":8,
        "settembre":9, "ottobre":10, "novembre":11, "dicembre":12
    }

    if mese_nome not in mesi:
        await update.message.reply_text("❌ Mese non valido")
        return

    mese = mesi[mese_nome]

    # 🔥 3. ora
    ora_raw = ora_raw.replace(",", ":").replace(".", ":")
    if ":" in ora_raw:
        ora, minuti = map(int, ora_raw.split(":"))
    else:
        ora = int(ora_raw)
        minuti = 0

    # 🔥 4. anno automatico
    anno = datetime.now().year

    dt = datetime(anno, mese, giorno, ora, minuti)

    # 🔥 5. descrizione pulita
    descrizione = testo.replace(match.group(0), "").strip()

    if not descrizione:
        descrizione = "Promemoria"

    # 💾 6. salva
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reminders
        (user_id, text, event_time)
        VALUES (?, ?, ?)
    """, (
        update.effective_user.id,
        descrizione,
        dt.isoformat()
    ))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Nuovo promemoria:\n"
        f"{descrizione}\n\n"
        f"📅 {dt.strftime('%d/%m/%Y %H:%M')}"
    )

    schedule_reminder(
        update.effective_user.id,
        descrizione,
        dt.isoformat()
)



app.add_handler(CommandHandler("fare", fare))


async def promemoria(update, context): #lista di tutti i promemoria

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id,text,event_time
        FROM reminders
        WHERE user_id=?
        ORDER BY event_time
        """,
        (update.effective_user.id,)
    )

    dati = cur.fetchall()

    conn.close()

    if not dati:
        await update.message.reply_text(
            "Nessun promemoria."
        )
        return

    testo = ""

    for riga in dati:

        dt = datetime.fromisoformat(
            riga[2]
        )

        testo += (
            f"{riga[0]}. "
            f"{riga[1]}\n"
            f"{dt.strftime('%d/%m/%Y %H:%M')}\n\n"
        )

    await update.message.reply_text(testo)

app.add_handler(
    CommandHandler(
        "promemoria",
        promemoria
    )
)


async def eliminapromemoria(update, context):  #elima un promemoria

    if not context.args:
        return

    id_prom = context.args[0]

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM reminders
        WHERE id=?
        AND user_id=?
        """,
        (
            id_prom,
            update.effective_user.id
        )
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "🗑️ Promemoria eliminato"
    )

app.add_handler(
    CommandHandler(
        "eliminapromemoria",
        eliminapromemoria
    )
)


def get_meteo_ivrea(): #meteo

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": 45.4668,
        "longitude": 8.0171,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min",
        "timezone": "Europe/Rome"
    }

    r = requests.get(url, params=params)
    data = r.json()

    code = data["daily"]["weathercode"][0]
    tmax = data["daily"]["temperature_2m_max"][0]
    tmin = data["daily"]["temperature_2m_min"][0]

    if code == 0:
        cond = "☀️ Sereno"
    elif code in [1,2]:
        cond = "⛅ Poco nuvoloso"
    elif code in [3]:
        cond = "☁️ Nuvoloso"
    elif code in [51,53,55,61,63,65]:
        cond = "🌧️ Pioggia"
    else:
        cond = "🌦️ Variabile"

    return f"📍 Ivrea oggi:\n{cond}\n🌡 Max {tmax}°C / Min {tmin}°C"


async def send_meteo(): #meteo

    testo = get_meteo_ivrea()

    # manda a tutti gli utenti che hanno promemoria
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT user_id FROM reminders")
    users = cur.fetchall()
    conn.close()

    for (user_id,) in users:
        await app.bot.send_message(chat_id=user_id, text=testo)


def schedule_meteo():

    now = datetime.now()

    run_time = now.replace(hour=7, minute=30, second=0, microsecond=0)

    if run_time < now:
        run_time = run_time + timedelta(days=1)

    scheduler.add_job(
        send_meteo,
        "date",
        run_date=run_time
    )


def schedule_daily_meteo():

    schedule_meteo()

    scheduler.add_job(
        schedule_daily_meteo,
        "date",
        run_date=datetime.now() + timedelta(days=1)
    )


async def meteo(update, context): #comando meteo (/meteo)

    testo = get_meteo_ivrea()

    await update.message.reply_text(testo)
app.add_handler(CommandHandler("meteo", meteo))




print("Bot online...") #QUESTE RIGHE DEVONO RIMANERE PER ULTIME!!!!
if __name__ == "__main__":
    scheduler.start()
    schedule_daily_meteo()   # 🔥 AGGIUNTO METEO
    load_reminders_from_db()   # DATABASE CHE TIENE I DATI ACNHE DOPO IL RIAVVIO
    app.run_polling()
