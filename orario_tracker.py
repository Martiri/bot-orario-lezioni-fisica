import json
import os
import re
import csv
import sys
import unicodedata
import urllib.request
import urllib.parse
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Percorsi file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
PREVIOUS_SCHEDULE_FILE = os.path.join(DATA_DIR, "previous_schedule.json")

# File generati e scaricabili
OUTPUT_CSV = os.path.join(BASE_DIR, "orario_lezioni.csv")
OUTPUT_MD_OGGI = os.path.join(BASE_DIR, "orario_oggi.md")
OUTPUT_MD_SETTIMANA = os.path.join(BASE_DIR, "orario_settimana.md")
OUTPUT_MD_COMPLETO = os.path.join(BASE_DIR, "orario_completo.md")
OUTPUT_ICS = os.path.join(BASE_DIR, "orario_lezioni.ics")
OUTPUT_HTML = os.path.join(BASE_DIR, "orario_lezioni.html")

ROME_TZ = ZoneInfo("Europe/Rome")

GIORNI_SETTIMANA = {
    0: "Lunedì",
    1: "Martedì",
    2: "Mercoledì",
    3: "Giovedì",
    4: "Venerdì",
    5: "Sabato",
    6: "Domenica"
}

def load_config():
    """Carica la configurazione da config.json ed eventuali variabili d'ambiente."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
        
    env_canale = os.getenv("CANALE")
    if env_canale:
        cfg["canale"] = env_canale.strip().upper()
        
    return cfg

def normalize_text(text: str) -> str:
    """Rimuove accenti e trasforma in minuscolo per confronti robusti."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()

def extract_channel(title: str, cod_sdoppiamento: str = "") -> str:
    """Estrae l'eventuale canale (A-L o M-Z) dal titolo dell'insegnamento o dal codice sdoppiamento."""
    combined = f"{title} {cod_sdoppiamento}".upper()
    if "(A-L)" in combined or "A-L" in combined:
        return "A-L"
    elif "(M-Z)" in combined or "M-Z" in combined:
        return "M-Z"
    return "TUTTI"

def clean_course_name(title: str) -> str:
    """Pulisce il nome del corso togliendo tag di moduli e canali per una lettura agevole."""
    t = title
    t = re.sub(r"/\s*\([0-9]+\)\s*Modulo\s*[0-9]+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"/\s*\([A-Z]-[A-Z]\)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def matches_target_courses(title: str, target_courses: list) -> bool:
    norm_title = normalize_text(title)
    for c in target_courses:
        if normalize_text(c) in norm_title:
            return True
    return False

def filter_by_channel(event_channel: str, user_channel: str) -> bool:
    if not user_channel or user_channel in ("ALL", "TUTTI"):
        return True
    if event_channel == "TUTTI":
        return True
    return event_channel == user_channel

def fetch_schedule(api_url: str, anno: int, curricula: str, start_date: str, end_date: str) -> list:
    """
    Interroga l'API UniBo a blocchi di 30 giorni.
    Questo evita errori 500 generati dal server Plone quando si richiedono periodi troppo lunghi.
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    all_events = []
    chunk_start = start_dt
    
    while chunk_start < end_dt:
        chunk_end = min(chunk_start + timedelta(days=30), end_dt)
        params = {
            "anno": str(anno),
            "curricula": curricula,
            "start": chunk_start.strftime("%Y-%m-%d"),
            "end": chunk_end.strftime("%Y-%m-%d")
        }
        query_str = urllib.parse.urlencode(params)
        url = f"{api_url}?{query_str}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (UniBoPhysicsScheduleTracker)"})
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    all_events.extend(data)
        except Exception as e:
            print(f"[WARN] Errore nel download blocco {chunk_start} -> {chunk_end}: {e}")
            
        chunk_start = chunk_end + timedelta(days=1)
        
    return all_events

def parse_events(raw_events: list, target_courses: list, user_channel: str) -> list:
    """Filtra, pulisce e ordina le lezioni restituite dall'API."""
    parsed = []
    seen = set()
    
    for ev in raw_events:
        title = ev.get("title", "")
        if not matches_target_courses(title, target_courses):
            continue
            
        channel = extract_channel(title, ev.get("cod_sdoppiamento", ""))
        if not filter_by_channel(channel, user_channel):
            continue
            
        start_str = ev.get("start", "")
        end_str = ev.get("end", "")
        if not start_str or not end_str:
            continue
            
        dt_start = datetime.fromisoformat(start_str)
        dt_end = datetime.fromisoformat(end_str)
        lesson_date = dt_start.strftime("%Y-%m-%d")
        time_str = f"{dt_start.strftime('%H:%M')} - {dt_end.strftime('%H:%M')}"
        
        aule_nomi = []
        aule_indirizzi = []
        for a in ev.get("aule", []):
            nome = a.get("des_risorsa") or a.get("des_edificio") or "Aula da definire"
            ind = a.get("des_indirizzo") or a.get("des_ubicazione") or ""
            aule_nomi.append(nome.strip())
            if ind:
                aule_indirizzi.append(ind.strip())
                
        aula_str = " / ".join(dict.fromkeys(aule_nomi)) if aule_nomi else "Aula da definire"
        indirizzo_str = " / ".join(dict.fromkeys(aule_indirizzi)) if aule_indirizzi else ""
        docente = (ev.get("docente") or "Non specificato").strip()
        note = (ev.get("note") or "").strip()
        cleaned_title = clean_course_name(title)
        
        lesson = {
            "id": f"{lesson_date}_{cleaned_title}_{channel}_{time_str}",
            "data": lesson_date,
            "giorno": GIORNI_SETTIMANA[dt_start.weekday()],
            "ora_inizio": dt_start.strftime("%H:%M"),
            "ora_fine": dt_end.strftime("%H:%M"),
            "orario": time_str,
            "corso": cleaned_title,
            "corso_completo": title,
            "canale": channel,
            "docente": docente,
            "aula": aula_str,
            "indirizzo": indirizzo_str,
            "note": note,
            "start_iso": start_str,
            "end_iso": end_str
        }
        
        if lesson["id"] not in seen:
            seen.add(lesson["id"])
            parsed.append(lesson)
            
    parsed.sort(key=lambda x: (x["data"], x["ora_inizio"], x["corso"]))
    return parsed

def detect_schedule_changes(prev_lessons: list, curr_lessons: list, today_str: str) -> list:
    """
    Rileva variazioni tra la precedente esecuzione e quella odierna:
    - Cambi di aula
    - Cambi di orario
    - Lezioni cancellate o anticipate/posticipate
    - Nuove lezioni inserite
    """
    if not prev_lessons:
        return []
        
    changes = []
    
    # Mappiamo le lezioni future (da oggi compreso in poi)
    # Chiave univoca della lezione su base giornaliera
    prev_map = {
        f"{x['data']}_{normalize_text(x['corso'])}_{x['canale']}": x 
        for x in prev_lessons if x['data'] >= today_str
    }
    curr_map = {
        f"{x['data']}_{normalize_text(x['corso'])}_{x['canale']}": x 
        for x in curr_lessons if x['data'] >= today_str
    }
    
    # 1. Verifica modifiche o cancellazioni per lezioni precedentemente note
    for key, prev_item in prev_map.items():
        if key in curr_map:
            curr_item = curr_map[key]
            # Controllo cambio aula
            if prev_item["aula"] != curr_item["aula"]:
                changes.append({
                    "tipo": "CAMBIO_AULA",
                    "data": curr_item["data"],
                    "giorno": curr_item["giorno"],
                    "corso": curr_item["corso"],
                    "canale": curr_item["canale"],
                    "vecchio": prev_item["aula"],
                    "nuovo": curr_item["aula"],
                    "orario": curr_item["orario"],
                    "dettagli": f"Il {curr_item['data']} ({curr_item['giorno']}), '{curr_item['corso']}' ({curr_item['orario']}) ha cambiato aula: da '{prev_item['aula']}' a '{curr_item['aula']}'"
                })
            # Controllo cambio orario
            if prev_item["orario"] != curr_item["orario"]:
                changes.append({
                    "tipo": "CAMBIO_ORARIO",
                    "data": curr_item["data"],
                    "giorno": curr_item["giorno"],
                    "corso": curr_item["corso"],
                    "canale": curr_item["canale"],
                    "vecchio": prev_item["orario"],
                    "nuovo": curr_item["orario"],
                    "aula": curr_item["aula"],
                    "dettagli": f"Il {curr_item['data']} ({curr_item['giorno']}), '{curr_item['corso']}' ha cambiato orario: da '{prev_item['orario']}' a '{curr_item['orario']}' (Aula: {curr_item['aula']})"
                })
            # Controllo note/avvisi del docente
            if curr_item["note"] and curr_item["note"] != prev_item.get("note", ""):
                changes.append({
                    "tipo": "NUOVA_NOTA",
                    "data": curr_item["data"],
                    "giorno": curr_item["giorno"],
                    "corso": curr_item["corso"],
                    "canale": curr_item["canale"],
                    "vecchio": prev_item.get("note", ""),
                    "nuovo": curr_item["note"],
                    "dettagli": f"Avviso docente per '{curr_item['corso']}' del {curr_item['data']}: {curr_item['note']}"
                })
        else:
            # Lezione cancellata o spostata di data
            changes.append({
                "tipo": "CANCELLAZIONE",
                "data": prev_item["data"],
                "giorno": prev_item["giorno"],
                "corso": prev_item["corso"],
                "canale": prev_item["canale"],
                "vecchio": f"{prev_item['orario']} in {prev_item['aula']}",
                "nuovo": "NON PIÙ IN CALENDARIO",
                "dettagli": f"⚠️ LEZIONE ANNULLATA: '{prev_item['corso']}' del {prev_item['data']} ({prev_item['giorno']} {prev_item['orario']}) in {prev_item['aula']} non è più presente in calendario."
            })
            
    # 2. Controllo nuove lezioni comparse
    for key, curr_item in curr_map.items():
        if key not in prev_map:
            changes.append({
                "tipo": "NUOVA_LEZIONE",
                "data": curr_item["data"],
                "giorno": curr_item["giorno"],
                "corso": curr_item["corso"],
                "canale": curr_item["canale"],
                "vecchio": None,
                "nuovo": f"{curr_item['orario']} in {curr_item['aula']}",
                "dettagli": f"🆕 NUOVA LEZIONE: '{curr_item['corso']}' programmata per il {curr_item['data']} ({curr_item['giorno']} {curr_item['orario']}) in {curr_item['aula']}."
            })
            
    return changes

def export_csv(schedule: list, file_path: str):
    """Esporta la tabella in formato CSV UTF-8 (compatibile con Excel/Google Sheets)."""
    fields = ["Data", "Giorno", "Orario", "Insegnamento", "Canale", "Docente", "Aula", "Indirizzo", "Note"]
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for item in schedule:
            writer.writerow([
                item["data"],
                item["giorno"],
                item["orario"],
                item["corso"],
                item["canale"],
                item["docente"],
                item["aula"],
                item["indirizzo"],
                item["note"]
            ])

def export_markdown_table(schedule: list, title: str, file_path: str):
    """Esporta la tabella in formato Markdown leggibile in GitHub o viewer markdown."""
    lines = [f"# {title}\n"]
    if not schedule:
        lines.append("_Nessuna lezione programmata per questo periodo._\n")
    else:
        lines.append("| Data | Giorno | Orario | Insegnamento | Canale | Aula | Indirizzo | Docente | Note |")
        lines.append("| :--- | :--- | :--- | :--- | :---: | :--- | :--- | :--- | :--- |")
        for item in schedule:
            note_str = item['note'] if item['note'] else "-"
            lines.append(f"| {item['data']} | {item['giorno']} | **{item['orario']}** | **{item['corso']}** | {item['canale']} | {item['aula']} | {item['indirizzo']} | {item['docente']} | {note_str} |")
        lines.append("\n")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def export_html_table(schedule: list, title: str, file_path: str):
    """Genera una tabella HTML responsive con filtri visivi."""
    rows = []
    for item in schedule:
        note_cell = f"<span class='note-text'>⚠️ {item['note']}</span>" if item['note'] else ""
        rows.append(f"""
        <tr>
            <td data-label="Data"><strong>{item['data']}</strong><br><span class="day-badge">{item['giorno']}</span></td>
            <td data-label="Orario"><span class="badge time">{item['orario']}</span></td>
            <td data-label="Insegnamento"><strong>{item['corso']}</strong></td>
            <td data-label="Canale"><span class="badge channel">{item['canale']}</span></td>
            <td data-label="Aula & Sede"><strong>{item['aula']}</strong><br><small class="text-muted">{item['indirizzo']}</small></td>
            <td data-label="Docente">{item['docente']}</td>
            <td data-label="Note">{note_cell}</td>
        </tr>
        """)
    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 24px; background: #f8f9fa; color: #212529; }}
  h1 {{ color: #bb2e29; margin-bottom: 4px; }}
  p.subtitle {{ color: #6c757d; margin-top: 0; }}
  .container {{ background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); padding: 20px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #e9ecef; }}
  th {{ background-color: #f1f3f5; font-weight: 600; color: #495057; }}
  tr:hover {{ background-color: #f8f9fa; }}
  .badge {{ padding: 4px 10px; border-radius: 6px; font-size: 0.85em; font-weight: 600; display: inline-block; }}
  .time {{ background: #e3f2fd; color: #0d47a1; }}
  .channel {{ background: #e8f5e9; color: #1b5e20; }}
  .day-badge {{ color: #495057; font-size: 0.9em; }}
  .text-muted {{ color: #6c757d; }}
  .note-text {{ color: #d9480f; font-weight: 500; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>🎓 {title}</h1>
<p class="subtitle">Tracciamento orari Fisica UniBo (Bologna) - Generato in automatico via GitHub Actions</p>
<div class="container">
<table>
<thead>
<tr>
  <th>Data & Giorno</th><th>Orario</th><th>Insegnamento</th><th>Canale</th><th>Aula & Indirizzo</th><th>Docente</th><th>Note</th>
</tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>
</body>
</html>"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

def export_ics(schedule: list, file_path: str):
    """Genera file iCalendar (.ics) importabile direttamente su smartphone o Google Calendar."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UniBo Physics Timetable Tracker//IT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Orario Fisica UniBo",
        "X-WR-TIMEZONE:Europe/Rome"
    ]
    
    for item in schedule:
        dt_s = datetime.fromisoformat(item["start_iso"]).strftime("%Y%m%dT%H%M%S")
        dt_e = datetime.fromisoformat(item["end_iso"]).strftime("%Y%m%dT%H%M%S")
        summary = f"{item['corso']} [{item['canale']}]" if item['canale'] != 'TUTTI' else item['corso']
        location = f"{item['aula']}, {item['indirizzo']}".strip(", ")
        desc = f"Docente: {item['docente']}\\nAula: {item['aula']}\\nNote: {item['note']}"
        uid = f"{item['id']}@unibo-physics"
        
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.now(ROME_TZ).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;TZID=Europe/Rome:{dt_s}",
            f"DTEND;TZID=Europe/Rome:{dt_e}",
            f"SUMMARY:{summary}",
            f"LOCATION:{location}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT"
        ])
        
    lines.append("END:VCALENDAR")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))

def send_telegram_notification(token: str, chat_id: str, message_text: str, files_to_send: list):
    """Invia il riassunto della notifica su Telegram e allega i file CSV e ICS scaricabili con 1 tap."""
    base_url = f"https://api.telegram.org/bot{token}"
    
    # Tronca se supera il limite Telegram (4096 caratteri)
    if len(message_text) > 4000:
        message_text = message_text[:3950] + "\n\n<i>...elenco troncato per limite caratteri. Scarica la tabella CSV allegata per i dettagli completi.</i>"
        
    # 1. Invia messaggio di testo
    msg_url = f"{base_url}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(msg_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req) as resp:
            print("[INFO] Notifica Telegram inviata con successo!")
    except Exception as e:
        print(f"[ERROR] Errore invio messaggio Telegram: {e}")
        return

    # 2. Invia i documenti allegati scaricabili
    for file_path in files_to_send:
        if not os.path.exists(file_path):
            continue
        filename = os.path.basename(file_path)
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            
        body = []
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="chat_id"'.encode("utf-8"))
        body.append(b"")
        body.append(str(chat_id).encode("utf-8"))
        
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"'.encode("utf-8"))
        body.append(b"Content-Type: application/octet-stream")
        body.append(b"")
        body.append(file_bytes)
        body.append(f"--{boundary}--".encode("utf-8"))
        body.append(b"")
        
        full_body = b"\r\n".join(body)
        doc_url = f"{base_url}/sendDocument"
        req = urllib.request.Request(
            doc_url, 
            data=full_body, 
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                print(f"[INFO] Allegato {filename} inviato con successo su Telegram!")
        except Exception as e:
            print(f"[WARN] Impossibile inviare allegato {filename} su Telegram: {e}")

def send_ntfy_notification(topic: str, message_text: str, title: str):
    """Invia notifica push su smartphone via ntfy.sh (senza registrazione né bot)."""
    url = f"https://ntfy.sh/{topic}"
    data = message_text.encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Title": title,
        "Priority": "high",
        "Tags": "school_satchel,bell"
    })
    try:
        with urllib.request.urlopen(req) as resp:
            print("[INFO] Notifica ntfy.sh inviata con successo!")
    except Exception as e:
        print(f"[WARN] Errore invio ntfy.sh: {e}")

def build_notification_text(today_lessons: list, week_lessons: list, changes: list, is_first_run: bool, now_dt: datetime) -> str:
    """Formatta il messaggio di notifica delle 8:00 del mattino."""
    date_str = now_dt.strftime("%d/%m/%Y")
    day_name = GIORNI_SETTIMANA[now_dt.weekday()]
    
    parts = []
    parts.append(f"<b>📚 ORARIO LEZIONI FISICA - {day_name} {date_str}</b>\n")
    
    # 1. VARIAZIONI DI AULA O ORARIO (Massima visibilità)
    if is_first_run:
        parts.append("ℹ️ <i>Prima esecuzione: calendario inizializzato con successo. Da domani riceverai un avviso immediato per qualsiasi modifica di aula o orario.</i>\n")
    elif changes:
        parts.append("🚨 <b>ATTENZIONE: RILEVATE VARIAZIONI!</b>")
        for ch in changes[:8]:  # Mostra fino a 8 modifiche nel messaggio testuale
            if ch["tipo"] == "CAMBIO_AULA":
                parts.append(f"• 🏛️ <b>CAMBIO AULA</b> - <b>{ch['corso']}</b>:\n  Il {ch['data']} ({ch['giorno']} {ch['orario']}):\n  Da: <s>{ch['vecchio']}</s>\n  ➡️ A: <b>{ch['nuovo']}</b>")
            elif ch["tipo"] == "CAMBIO_ORARIO":
                parts.append(f"• ⏰ <b>CAMBIO ORARIO</b> - <b>{ch['corso']}</b>:\n  Il {ch['data']} ({ch['giorno']}):\n  Da: <s>{ch['vecchio']}</s> ➡️ A: <b>{ch['nuovo']}</b>\n  Aula: {ch.get('aula', '')}")
            elif ch["tipo"] == "CANCELLAZIONE":
                parts.append(f"• ❌ <b>ANNULLAMENTO</b>:\n  {ch['dettagli']}")
            elif ch["tipo"] == "NUOVA_LEZIONE":
                parts.append(f"• 🆕 <b>NUOVA LEZIONE</b>:\n  {ch['dettagli']}")
            elif ch["tipo"] == "NUOVA_NOTA":
                parts.append(f"• 📝 <b>AVVISO DOCENTE</b>: {ch['dettagli']}")
        if len(changes) > 8:
            parts.append(f"<i>...e altre {len(changes)-8} variazioni (consulta il file CSV allegato).</i>")
        parts.append("")
    else:
        parts.append("✅ <i>Nessuna variazione di aula o orario rilevata.</i>\n")
        
    # 2. LEZIONI DI OGGI
    parts.append(f"<b>📅 Lezioni di Oggi ({day_name}):</b>")
    if not today_lessons:
        parts.append("🏖️ <i>Nessuna lezione in programma per oggi.</i>\n")
    else:
        for l in today_lessons:
            chan_badge = f" [{l['canale']}]" if l['canale'] != "TUTTI" else ""
            parts.append(f"• <b>{l['orario']}</b> | <b>{l['corso']}</b>{chan_badge}")
            parts.append(f"   🏛️ <b>{l['aula']}</b>")
            if l['indirizzo']:
                parts.append(f"   📍 <small>{l['indirizzo']}</small>")
            parts.append(f"   👨‍🏫 {l['docente']}")
            if l['note']:
                parts.append(f"   ⚠️ <i>Nota: {l['note']}</i>")
            parts.append("")
            
    # 3. PROSSIME LEZIONI DELLA SETTIMANA
    if not today_lessons and week_lessons:
        parts.append("<b>🗓️ Prossime lezioni nei prossimi giorni:</b>")
        for l in week_lessons[:5]:
            chan_badge = f" [{l['canale']}]" if l['canale'] != "TUTTI" else ""
            parts.append(f"• {l['giorno']} {l['data'][8:10]}/{l['data'][5:7]} ({l['orario']}): <b>{l['corso']}</b>{chan_badge} in {l['aula']}")
        parts.append("")

    parts.append("📎 <i>In allegato la tabella aggiornata in formato CSV (apribile in Excel) e il file calendario .ICS.</i>")
    return "\n".join(parts)

def build_issue_markdown(today_lessons, week_lessons, changes, is_first_run, now_dt):
    """Costruisce il titolo e il corpo formattato in Markdown per la Issue di GitHub."""
    date_str = now_dt.strftime("%d/%m/%Y")
    day_name = GIORNI_SETTIMANA[now_dt.weekday()]
    
    if changes:
        title = f"🚨 Variazione Orario/Aula — Fisica Triennale ({date_str})"
    elif today_lessons:
        title = f"📚 Orario Lezioni — {day_name} {date_str}"
    else:
        title = f"🗓️ Orario Lezioni — Settimana del {date_str}"
        
    lines = []
    lines.append(f"# 🎓 Orario Lezioni Fisica (UniBo) — {day_name} {date_str}\n")
    
    # 1. VARIAZIONI DI AULA O ORARIO
    if is_first_run:
        lines.append("> [!NOTE]")
        lines.append("> **Inizializzazione completata**: Il calendario è stato registrato. Da domani qualsiasi spostamento di aula o modifica di orario verrà evidenziato qui con massima priorità.\n")
    elif changes:
        lines.append("> [!WARNING]")
        lines.append(f"> ### 🚨 Rilevate {len(changes)} variazioni rispetto al calendario precedente!\n")
        for ch in changes:
            if ch["tipo"] == "CAMBIO_AULA":
                lines.append(f"- 🏛️ **CAMBIO AULA** — **{ch['corso']}** ({ch['data']}, {ch['giorno']} {ch['orario']}):")
                lines.append(f"  - Vecchia aula: ~~{ch['vecchio']}~~")
                lines.append(f"  - **Nuova aula**: **{ch['nuovo']}**")
            elif ch["tipo"] == "CAMBIO_ORARIO":
                lines.append(f"- ⏰ **CAMBIO ORARIO** — **{ch['corso']}** ({ch['data']}, {ch['giorno']}):")
                lines.append(f"  - Vecchio orario: ~~{ch['vecchio']}~~")
                lines.append(f"  - **Nuovo orario**: **{ch['nuovo']}** (Aula: {ch.get('aula', '-')})")
            elif ch["tipo"] == "CANCELLAZIONE":
                lines.append(f"- ❌ **ANNULLAMENTO**: {ch['dettagli']}")
            elif ch["tipo"] == "NUOVA_LEZIONE":
                lines.append(f"- 🆕 **NUOVA LEZIONE**: {ch['dettagli']}")
            elif ch["tipo"] == "NUOVA_NOTA":
                lines.append(f"- 📝 **AVVISO**: {ch['dettagli']}")
        lines.append("")
    else:
        lines.append("> [!TIP]")
        lines.append("> ✅ **Nessuna variazione**: Tutte le aule e gli orari sono confermati rispetto all'ultimo controllo.\n")
        
    # 2. LEZIONI DI OGGI
    lines.append(f"## 📅 Lezioni di Oggi ({day_name} {date_str})\n")
    if not today_lessons:
        lines.append("🏖️ *Nessuna lezione in programma per oggi.*\n")
    else:
        lines.append("| Orario | Insegnamento | Canale | Aula | Docente | Note |")
        lines.append("| :--- | :--- | :---: | :--- | :--- | :--- |")
        for l in today_lessons:
            chan = l['canale'] if l['canale'] != "TUTTI" else "Tutti"
            aula_info = l['aula']
            if l.get('indirizzo'):
                aula_info += f"<br><small>📍 {l['indirizzo']}</small>"
            note_info = l.get('note', '') or '-'
            lines.append(f"| **{l['orario']}** | **{l['corso']}** | `{chan}` | {aula_info} | {l['docente']} | {note_info} |")
        lines.append("")
        
    # 3. PROSSIME LEZIONI DELLA SETTIMANA
    lines.append("## 🗓️ Prossime Lezioni nei Prossimi 7 Giorni\n")
    if not week_lessons:
        lines.append("*Nessuna lezione in programma nei prossimi 7 giorni.*\n")
    else:
        lines.append("| Data | Giorno | Orario | Insegnamento | Canale | Aula |")
        lines.append("| :--- | :--- | :--- | :--- | :---: | :--- |")
        for l in week_lessons[:15]:
            chan = l['canale'] if l['canale'] != "TUTTI" else "Tutti"
            d_fmt = f"{l['data'][8:10]}/{l['data'][5:7]}"
            lines.append(f"| {d_fmt} | {l['giorno']} | {l['orario']} | {l['corso']} | `{chan}` | {l['aula']} |")
        if len(week_lessons) > 15:
            lines.append(f"| ... | ... | ... | *Altre {len(week_lessons)-15} lezioni nel file CSV* | | |")
        lines.append("")
        
    # 4. DOWNLOAD E TABELLE
    repo_name = os.getenv("GITHUB_REPOSITORY", "Martiri/bot-orario-lezioni-fisica")
    raw_base = f"https://raw.githubusercontent.com/{repo_name}/main"
    blob_base = f"https://github.com/{repo_name}/blob/main"
    owner = os.getenv("GITHUB_REPOSITORY_OWNER") or (repo_name.split("/")[0] if "/" in repo_name else "Martiri")

    lines.append("---")
    lines.append("### 📥 Tabelle e Calendari Scaricabili")
    lines.append(f"- 📅 **Calendario iCal (Google / Apple / Outlook)**: [📲 Scarica / Aggiungi `orario_lezioni.ics`]({raw_base}/orario_lezioni.ics)")
    lines.append(f"- 📊 **Tabella CSV (Excel / Sheets)**: [📥 Scarica `orario_lezioni.csv`]({raw_base}/orario_lezioni.csv) • [Visualizza su GitHub]({blob_base}/orario_lezioni.csv)")
    lines.append(f"- 🌐 **Pagina Web Interattiva**: [Visualizza `orario_lezioni.html`]({blob_base}/orario_lezioni.html)")
    lines.append(f"- 📄 **Elenco Testuale di Oggi**: [Visualizza `orario_oggi.md`]({blob_base}/orario_oggi.md)")
    lines.append(f"\n*Notifica generata automaticamente per @{owner} dal Tracciatore Orari Lezioni UniBo.*")
    
    return title, "\n".join(lines)

def invia_issue_github(titolo, corpo, labels=None):
    """Crea una nuova Issue nel repository GitHub assegnata all'utente per garantire l'invio immediato della notifica email."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("[INFO] GITHUB_TOKEN o GITHUB_REPOSITORY non presenti (salto creazione Issue GitHub).")
        return False

    if labels is None:
        labels = ["orario-lezioni"]

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "OrarioFisicaBot",
        "Content-Type": "application/json"
    }

    owner = os.environ.get("GITHUB_REPOSITORY_OWNER") or (repo.split("/")[0] if "/" in repo else "Martiri")

    # 1. Chiudi tutte le issue precedenti aperte con questa etichetta per mantenere pulito il repository
    try:
        label_query = labels[0] if labels else "orario-lezioni"
        list_url = f"https://api.github.com/repos/{repo}/issues?labels={label_query}&state=open&per_page=30"
        req = urllib.request.Request(list_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                issues = json.loads(resp.read().decode("utf-8"))
                for iss in issues:
                    close_url = f"https://api.github.com/repos/{repo}/issues/{iss['number']}"
                    close_req = urllib.request.Request(
                        close_url,
                        data=json.dumps({"state": "closed"}).encode("utf-8"),
                        headers=headers,
                        method="PATCH"
                    )
                    try:
                        with urllib.request.urlopen(close_req, timeout=10) as cresp:
                            if cresp.status == 200:
                                print(f"[INFO] Chiusa precedente issue archiviata #{iss['number']}")
                    except Exception:
                        pass
    except Exception as e:
        print(f"[WARN] Impossibile verificare/chiudere issue precedenti: {e}")

    # 2. Crea SEMPRE una NUOVA Issue assegnata all'owner
    # In GitHub, l'apertura di una nuova issue con assegnatario genera l'invio dell'email di notifica con il corpo completo della issue
    create_url = f"https://api.github.com/repos/{repo}/issues"
    payload = {
        "title": titolo,
        "body": corpo,
        "labels": labels,
        "assignees": [owner] if owner else []
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    
    try:
        req = urllib.request.Request(create_url, data=data_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                res_data = json.loads(resp.read().decode("utf-8"))
                print(f"[SUCCESS] Issue GitHub creata con successo: #{res_data.get('number')} - {titolo}")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 422:
            # Fallback se assignees o labels non sono accettati
            print("[WARN] Fallback creazione issue senza assignees/labels...")
            payload_fallback = {
                "title": titolo,
                "body": corpo
            }
            try:
                fb_bytes = json.dumps(payload_fallback).encode("utf-8")
                req = urllib.request.Request(create_url, data=fb_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status in (200, 201):
                        res_data = json.loads(resp.read().decode("utf-8"))
                        print(f"[SUCCESS] Issue GitHub creata con fallback: #{res_data.get('number')} - {titolo}")
                        return True
            except Exception as e2:
                print(f"[ERRORE] Errore creazione Issue GitHub fallback: {e2}")
        else:
            print(f"[ERRORE] Errore HTTP creazione Issue GitHub ({e.code}): {e.reason}")
    except Exception as e:
        print(f"[ERRORE] Errore connessione Issue GitHub: {e}")
    return False

def main():
    cfg = load_config()
    os.makedirs(DATA_DIR, exist_ok=True)
    
    now_rome = datetime.now(ROME_TZ)
    today_str = now_rome.strftime("%Y-%m-%d")
    
    print(f"[INFO] Avvio tracciamento orari Fisica (UniBo)")
    print(f"[INFO] Data e ora attuale a Roma: {today_str} {now_rome.strftime('%H:%M:%S')}")
    print(f"[INFO] Canale impostato: {cfg.get('canale', 'ALL')}")
    
    # Esecuzione e notifica sempre attive ad ogni ciclo (comportamento identico a bot-bandi-unibo)
    allow_notification = True

    # Finestra di interrogazione: ultimi 7 giorni fino a +120 giorni (copre l'intero semestre)
    start_date = (now_rome.date() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = (now_rome.date() + timedelta(days=120)).strftime("%Y-%m-%d")
    
    print(f"[INFO] Download orari dall'API ({start_date} -> {end_date})...")
    raw_events = fetch_schedule(
        api_url=cfg["api_url"],
        anno=cfg["anno_di_corso"],
        curricula=cfg["curricula"],
        start_date=start_date,
        end_date=end_date
    )
    print(f"[INFO] Ricevuti {len(raw_events)} eventi totali dall'ateneo.")
    
    current_schedule = parse_events(raw_events, cfg["target_courses"], cfg.get("canale", "ALL"))
    print(f"[INFO] {len(current_schedule)} lezioni corrispondono ai corsi seguiti.")
    
    # Caricamento storico precedente
    previous_schedule = []
    is_first_run = True
    if os.path.exists(PREVIOUS_SCHEDULE_FILE):
        try:
            with open(PREVIOUS_SCHEDULE_FILE, "r", encoding="utf-8") as f:
                state_data = json.load(f)
                # Verifica compatibilità canale per evitare falsi positivi al cambio canale
                if isinstance(state_data, dict) and state_data.get("canale") == cfg.get("canale"):
                    previous_schedule = state_data.get("lessons", [])
                    is_first_run = False
                elif isinstance(state_data, list):
                    previous_schedule = state_data
                    is_first_run = False
        except Exception as e:
            print(f"[WARN] Impossibile leggere {PREVIOUS_SCHEDULE_FILE}: {e}")
            is_first_run = True
            
    # Rilevamento variazioni
    changes = detect_schedule_changes(previous_schedule, current_schedule, today_str)
    if changes:
        print(f"[AVVISO] Trovate {len(changes)} variazioni di orario o aula!")
        for ch in changes:
            print("  *", ch["dettagli"])
    else:
        print("[INFO] Nessuna variazione rilevata rispetto al calendario precedente.")
        
    # Salvataggio dello stato attuale strutturato
    state_to_save = {
        "canale": cfg.get("canale", "ALL"),
        "last_updated": now_rome.isoformat(),
        "lessons": current_schedule
    }
    with open(PREVIOUS_SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(state_to_save, f, indent=2, ensure_ascii=False)
    print(f"[INFO] Stato aggiornato salvato in {PREVIOUS_SCHEDULE_FILE}")
    
    # Generazione tabelle e file
    today_lessons = [l for l in current_schedule if l["data"] == today_str]
    week_end_str = (now_rome.date() + timedelta(days=7)).strftime("%Y-%m-%d")
    week_lessons = [l for l in current_schedule if today_str <= l["data"] <= week_end_str]
    
    export_csv(current_schedule, OUTPUT_CSV)
    export_markdown_table(today_lessons, f"Lezioni di Oggi - {GIORNI_SETTIMANA[now_rome.weekday()]} {today_str}", OUTPUT_MD_OGGI)
    export_markdown_table(week_lessons, f"Orario della Settimana ({today_str} - {week_end_str})", OUTPUT_MD_SETTIMANA)
    export_markdown_table(current_schedule, "Calendario Completo Lezioni", OUTPUT_MD_COMPLETO)
    export_html_table(current_schedule, f"Orario Lezioni Fisica 3° Anno - Aggiornato al {today_str}", OUTPUT_HTML)
    export_ics(current_schedule, OUTPUT_ICS)
    
    print(f"[INFO] File generati con successo:")
    print(f"  - CSV scaricabile: {OUTPUT_CSV}")
    print(f"  - Calendario iCal: {OUTPUT_ICS}")
    print(f"  - HTML visuale:   {OUTPUT_HTML}")
    print(f"  - Markdown oggi:  {OUTPUT_MD_OGGI}")
    print(f"  - Markdown sett.: {OUTPUT_MD_SETTIMANA}")
    
    notification_html = build_notification_text(today_lessons, week_lessons, changes, is_first_run, now_rome)
    issue_title, issue_body = build_issue_markdown(today_lessons, week_lessons, changes, is_first_run, now_rome)
    
    # Scrittura riepilogo in GitHub Step Summary (se eseguito in GitHub Actions)
    github_step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if github_step_summary:
        try:
            with open(github_step_summary, "a", encoding="utf-8") as f:
                f.write(f"\n{issue_body}\n")
            print("[INFO] Riepilogo scritto con successo su GITHUB_STEP_SUMMARY")
        except Exception as e:
            print(f"[WARN] Impossibile scrivere su GITHUB_STEP_SUMMARY: {e}")

    if allow_notification:
        # 1. Notifica via GitHub Issue
        if os.getenv("CREATE_GITHUB_ISSUE", "true").lower() in ("true", "1", "yes"):
            print("[INFO] Creazione notifica via GitHub Issue...")
            invia_issue_github(issue_title, issue_body)

        # 2. Notifica via Telegram
        tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        ntfy_topic = os.getenv("NTFY_TOPIC")
        
        if tg_token and tg_chat_id:
            print("[INFO] Invio notifica via Telegram...")
            send_telegram_notification(tg_token, tg_chat_id, notification_html, [OUTPUT_CSV, OUTPUT_ICS])
        else:
            print("[INFO] TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID non configurati. Salto invio Telegram.")
            
        if ntfy_topic:
            print(f"[INFO] Invio notifica push via ntfy.sh ({ntfy_topic})...")
            plain_text = re.sub(r"<[^>]+>", "", notification_html)
            send_ntfy_notification(ntfy_topic, plain_text, f"Orario Fisica UniBo - {today_str}")
    else:
        print("[INFO] Notifica non inviata in questo orario.")

    print("\n--- ANTEPRIMA NOTIFICA DELLE 8:00 ---\n")
    print(re.sub(r"<[^>]+>", "", notification_html))
    print("---------------------------------------\n")

if __name__ == "__main__":
    main()
