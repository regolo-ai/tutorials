<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# AI Governance & Copyright Policy Gateway

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Code-Runnable_Examples-2ea44f.svg" alt="Code: Runnable Examples" />
  <img src="https://img.shields.io/badge/GPU-100%25_Ready-0078D4.svg" alt="GPU 100% Ready" />
  <img src="https://img.shields.io/badge/API-OpenAI_Compatible-313236.svg" alt="API OpenAI Compatible" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

Repository di esempio per un gateway di policy AI che intercetta prompt, applica regole di compliance e genera output sicuro.
Basato sull'articolo:
https://regolo.ai/ai-governance-copyright-and-enterprise-risk-how-to-build-a-policy-gateway-before-you-ship/

## Descrizione

Questo progetto illustra un pattern di governance AI:
- protocollo di classificazione prompt (BLOCK / ALLOW / TRANSFORM)
- removal automatico PII (email, telefono, codici identificativi)
- chiamata a Regolo `/models` e `/v1/chat/completions`
- flusso a due fasi: verifica policy + generazione risposta

È pensato come proof-of-concept per team enterprise che vogliono ridurre rischio copyright e dati sensibili prima della messa in produzione.

## Struttura del repository

- `main.py`: script principale con logica di policy gateway e generazione.
- `.env`: opzionale, passare `REGOLO_API_KEY`.
- `README.md`: questa documentazione.

## Requisiti

- Python 3.10+
- pacchetti: `requests`, opzionale `python-dotenv`
- variabile d'ambiente `REGOLO_API_KEY`

## Setup rapido

1. Clona il repo:

   ```bash
   git clone https://github.com/yourusername/tutorials.git
   cd tutorials/ai-governance-copyright
   ```

2. Crea virtualenv e installa dipendenze:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install requests python-dotenv
   ```

3. Imposta la chiave API:

   ```bash
   export REGOLO_API_KEY="your_token"
   # oppure crea .env con REGOLO_API_KEY=your_token
   ```

## Uso

Esegui lo script:

```bash
python3 main.py
```

Dovrebbe stampare:
- `POLICY_DECISION` con azione e prompt sicuro
- `SAFE_OUTPUT` con la risposta generata

## Personalizzazione

- `POLICY` in `main.py` contiene regole di blocco/consenti.
- `redact_pii()` rimuove email, numeri e telefoni.
- `choose_chat_model()` seleziona un modello preferito tra llama/qwen/gpt-oss.

## Estensioni consigliate

- aggiungere log di audit (UUID, timestamp, user_id)
- memorizzare decisioni policy in DB
- gestire input batch con limiti rate
- validazione JSON schema per `safe_prompt`

## Link Articolo

- Regolo Case Study: "AI Governance, Copyright and Enterprise Risk"
- URL: https://regolo.ai/ai-governance-copyright-and-enterprise-risk-how-to-build-a-policy-gateway-before-you-ship/

## Licenza

MIT.

### How to Use
1. Clone this repository: `git clone https://github.com/regolo-ai/tutorials.git`
2. Navigate to the desired tutorial folder.
3. Follow the instructions in the folder's README.md. 
4. Get a free API key from Regolo to run the code: [Sign Up for Free Trial](https://regolo.ai/pricing).
5. Run the code and see the results in minutes.
