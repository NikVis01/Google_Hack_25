# 🧠 Company AI Assistant — Google Hackathon 2025

A lightweight, FastAPI-powered backend paired with a React frontend, designed as a **company employee helper bot**. Built during the 2025 Google Hackathon, this project answers company-specific questions using structured documents and memory.

![image](https://github.com/user-attachments/assets/a98faeb3-b0a0-40ab-8353-0ecf3f600cae)

## 🚀 Features

- ✅ JSON-based company knowledge ingestion
- ✅ FastAPI backend with structured endpoints
- ✅ Frontend chat interface for querying the assistant
- ✅ Local run support for rapid development
- ✅ Minimal setup; no external dependencies beyond pip/npm

## 🛠️ Tech Stack

- **Backend**: Python 3, FastAPI, Uvicorn
- **Frontend**: React + Vite
- **Hosting**: Google Cloud VM

## 🔧 Setup

### Frontend
(Run locally or hosted)

npm install
npm run dev

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 gemini_agent.py
