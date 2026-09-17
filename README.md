# 🎓 Tracciatore Automatico Orario Lezioni - Laurea in Fisica (UniBo)

Sistema autonomo basato su **GitHub Actions** che interroga quotidianamente l'orario ufficiale del Corso di Laurea in Fisica dell'Università di Bologna (codice corso `9244`), rileva **qualsiasi modifica di aula o orario** rispetto al giorno precedente e invia una notifica alle **8:00 del mattino (orario italiano)** con la tabella aggiornata pronta per essere scaricata.

---

## 📌 Corsi Monitorati (3° Anno)

Il sistema monitora i seguenti insegnamenti:
1. **Meccanica Quantistica** (1° semestre)
2. **Fisica Nucleare e Subnucleare** (1° semestre)
3. **Fisica della Materia** (1° semestre)
4. **Laboratorio di Elettronica** (1° semestre)
5. **Attività Formativa e di Orientamento** (tirocinio/preparazione tesi)
6. **Astrofisica** (1° semestre)
7. **Introduzione alla Fisica dei Sistemi Complessi** (1° semestre)
8. **Elementi di Teoria della Relatività Generale** (2° semestre)
9. **Topics in Mathematical Methods and Models in Theoretical Physics** (2° semestre)

> [!NOTE]
> I corsi del 2° semestre (*Relatività Generale* e *Topics in Mathematical Methods*) verranno inclusi automaticamente nella tabella non appena l'ateneo pubblicherà gli orari definitivi del secondo periodo didattico.

---

## ⚡ Caratteristiche Principali

- 🤖 **100% Autonomo su GitHub**: Gira ogni giorno su GitHub Actions, senza bisogno di server o computer accesi.
- ⏰ **Notifica alle 8:00 (Ora Italiana)**: Gestisce automaticamente il cambio tra Ora Solare (CET) e Ora Legale (CEST).
- 🚨 **Rilevamento Modifiche**: Se un docente sposta un'aula, anticipa un orario o annulla una lezione, il sistema lo segnala in cima alla notifica evidenziando la variazione (`Da Aula X ➡️ A Aula Y`).
- 📥 **Tabelle Scaricabili Subito**:
  - `orario_lezioni.csv`: tabella esportata in formato foglio di calcolo (Excel, Numbers, Google Sheets).
  - `orario_lezioni.ics`: file calendario standard importabile su Google Calendar, Apple Calendar o Outlook con un tap.
  - `orario_lezioni.html`: pagina web visuale e stampabile con tabella orari.
  - `orario_oggi.md` e `orario_settimana.md`: riassunti rapidi in formato Markdown.
- 📲 **Download Diretto da Notifica**: Su Telegram il bot invia direttamente il messaggio e allega i file `.csv` e `.ics` in chat!

---

## 🚀 Guida all'Attivazione in 3 Passaggi

### 1. Crea il Bot Telegram per ricevere le notifiche (2 minuti)

1. Apri Telegram e cerca **`@BotFather`**.
2. Invia il comando `/newbot`, scegli un nome (es. `OrarioFisicaBot`) e uno username (es. `orario_fisica_franco_bot`).
3. BotFather ti fornirà un **HTTP API Token** (es. `123456789:ABCdefGhIJKlmNoPQRstuVWXyz`).
4. Avvia una chat con il tuo nuovo bot cliccando su **Avvia** (`/start`).
5. Per conoscere il tuo ID utente, cerca il bot **`@userinfobot`** su Telegram e premi `/start`: ti risponderà con il tuo `Id` numerico (es. `987654321`).

---

### 2. Configura i Secret su GitHub

Nel tuo repository GitHub:
1. Vai su **Settings** > **Secrets and variables** > **Actions**.
2. Clicca su **New repository secret** e aggiungi:
   - `TELEGRAM_BOT_TOKEN`: incolla il token fornito da BotFather.
   - `TELEGRAM_CHAT_ID`: incolla il tuo ID numerico.
   - *(Opzionale)* `CANALE`: inserisci `A-L` se appartieni al canale A-L, oppure `M-Z` se appartieni al canale M-Z. Lascia vuoto o imposta `ALL` per vedere entrambi i canali.

---

### 3. Abilita i permessi di scrittura per GitHub Actions

Per permettere a GitHub Actions di salvare lo storico dei cambiamenti e le tabelle nel repository:
1. Nel repository GitHub, vai su **Settings** > **Actions** > **General**.
2. Scorri fino alla sezione **Workflow permissions**.
3. Seleziona **Read and write permissions**.
4. Clicca su **Save**.

---

## 🧪 Esecuzione Manuale di Test

Puoi testare il tracciamento in qualsiasi momento:
1. Vai nella scheda **Actions** del repository GitHub.
2. Seleziona il workflow **Tracciamento Orario Lezioni Fisica UniBo**.
3. Clicca su **Run workflow**, seleziona il canale desiderato e premi il pulsante verde.
4. Riceverai la notifica e i file scaricabili direttamente sul tuo Telegram in pochi secondi!

---

## 📁 Struttura del Progetto

```text
├── .github/
│   └── workflows/
│       └── orario_lezioni.yml     # Workflow programmato alle 8:00 su GitHub Actions
├── data/
│   └── previous_schedule.json     # Storico delle lezioni per rilevare modifiche di aula/orario
├── config.json                    # Configurazione corso, anno e lista insegnamenti
├── orario_tracker.py              # Script principale Python (zero dipendenze esterne)
├── orario_lezioni.csv             # Tabella orari completa scaricabile in formato Excel/CSV
├── orario_lezioni.ics             # File calendario iCal per Google Calendar / Apple Calendar
├── orario_lezioni.html            # Tabella formattata in HTML responsive
├── orario_oggi.md                 # Tabella Markdown delle lezioni del giorno
└── orario_settimana.md            # Tabella Markdown della settimana corrente
```

---

## 💡 Alternativa Gratuita Senza Bot: Push via ntfy.sh

Se preferisci non usare Telegram:
1. Scarica l'app **ntfy** (gratuita per Android e iOS).
2. Scegli un nome per il tuo canale (es. `fisica_unibo_franco_2026`) e iscriviti nell'app.
3. Nei Secret di GitHub imposta `NTFY_TOPIC = fisica_unibo_franco_2026`.
4. Riceverai le notifiche push ogni mattina direttamente sullo smartphone!
