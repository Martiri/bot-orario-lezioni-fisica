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
- 📬 **Notifiche via GitHub Issues**: Crea automaticamente un'**Issue** nel repository con la tabella Markdown formattata delle lezioni di oggi, della settimana ed eventuali variazioni (funzionamento analogo a `bot-bandi-fisica`). Zero configurazioni richieste!
- 📊 **GitHub Actions Step Summary**: Mostra la tabella formattata direttamente nella schermata dell'esecuzione del workflow.
- 📥 **Tabelle Scaricabili Subito**:
  - `orario_lezioni.csv`: tabella esportata in formato foglio di calcolo (Excel, Numbers, Google Sheets).
  - `orario_lezioni.ics`: file calendario standard importabile su Google Calendar, Apple Calendar o Outlook con un tap.
  - `orario_lezioni.html`: pagina web visuale e stampabile con tabella orari.
  - `orario_oggi.md` e `orario_settimana.md`: riassunti rapidi in formato Markdown.
- 📲 **Notifiche Telegram (Opzionali)**: Invio opzionale su Telegram con i file `.csv` e `.ics` allegati in chat.

---

## 🚀 Funzionamento 100% Autonomo (Zero Configurazione)

Il bot è **immediatamente operativo** e configurato per funzionare in totale autonomia, esattamente come `bot-bandi-unibo`:

- **Nessun Secret da configurare**: Utilizza i permessi automatici `GITHUB_TOKEN` per aprire e aggiornare le Issue.
- **Nessun bot Telegram obbligatorio**: Ricevi gli aggiornamenti e gli avvisi direttamente nella scheda **Issues** del repository e via email da GitHub.
- **Aggiornamento quotidiano**: Il workflow si avvia ogni mattina in automatico su GitHub Actions:
  1. Scarica gli orari aggiornati dal portale di Ateneo per il Canale **M-Z** (corso `9244`).
  2. Rileva se ci sono stati cambi di aula, anticipi o cancellazioni rispetto al giorno precedente.
  3. Crea o aggiorna l'**Issue del giorno** con la tabella orari e l'evidenziazione delle variazioni.
  4. Salva e committa lo storico aggiornato nel repository.

---

## 🧪 Esecuzione Manuale (Opzionale)

Non devi fare nulla perché gira da solo ogni mattina. Se tuttavia vuoi forzare un controllo immediato a qualsiasi ora:
1. Vai nella scheda **Actions** del repository: [Actions](https://github.com/Martiri/bot-orario-lezioni-fisica/actions).
2. Seleziona **Tracciamento Orario Lezioni Fisica UniBo**.
3. Clicca su **Run workflow** > pulsante verde.
4. In meno di 30 secondi la Issue del giorno sarà creata/aggiornata!

---

## 📲 Notifiche Telegram (Facoltative)

Se oltre alle GitHub Issues desideri ricevere le notifiche anche su uno smartphone via Telegram:
1. Crea un bot con `@BotFather` e ottieni il Token.
2. Ricava il tuo ID con `@userinfobot`.
3. Aggiungi i secret `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` in **Settings** > **Secrets and variables** > **Actions**.
*(Se non li configuri, il bot funziona comunque regolarmente tramite GitHub Issues).*

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
