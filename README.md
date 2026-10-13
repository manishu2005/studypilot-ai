# AI Study Companion

AI Study Companion is an AI-powered learning assistant that helps students study from PDFs, PPTX files, and videos. It supports document ingestion, semantic retrieval, quiz generation, diagnostic assessment, and a learning dashboard.

This project contains:
- Backend API built with FastAPI
- Frontend dashboard/app built with React + Vite
- Local SQLite and Chroma vector database storage
- AI services powered by Gemini and/or Groq APIs

## Features
- Upload and process PDFs, PPTX files, and supported video files
- Search and retrieve relevant knowledge from uploaded material
- Generate quizzes and study guidance
- Track learner progress and dashboard metrics
- Use AI assessments and tutoring flows to improve learning outcomes

## Project structure

```text
AI-Study-Companinon/
├── backend/
│   ├── app/
│   ├── requirements.txt
│   ├── .env
│   ├── study_companion.db
│   ├── chroma_db/
│   └── sample_materials/
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── vite.config.js
│   └── .env
├── docs/
└── README.md
```

## Prerequisites

Before running the project, make sure you have:

- Python 3.10+ recommended
- Node.js 18+ and npm
- Git
- Access to API keys for Google Gemini and/or Groq (configured in the backend `.env` file)

## Dependencies

### Backend dependencies
The backend dependencies are managed in `backend/requirements.txt` and include:
- FastAPI
- Uvicorn
- Pydantic Settings
- ChromaDB
- Sentence Transformers
- PyMuPDF
- python-pptx
- Pillow
- Faster Whisper
- Google GenAI
- Pytest
- additional libraries for processing PDFs, PPTX, and video content

### Frontend dependencies
The frontend dependencies are managed with npm via `frontend/package.json` and include:
- React
- Vite
- React Router DOM
- Lucide React

## Setup instructions

### 1) Clone the repository

```bash
git clone <repository-url>
cd AI-Study-Companinon
```

### 2) Set up the backend

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

Windows (PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```

Windows (Command Prompt):
```cmd
.venv\Scripts\activate.bat
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Check the backend `.env` file and make sure required keys are present, for example:

```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
```

If the file is missing, create `backend/.env` and add your configuration there.

### 3) Set up the frontend

From the project root:

```bash
cd frontend
npm install
```

Make sure `frontend/.env` contains the API base URL:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Running the project

### Start the backend API

From the `backend` directory:

```bash
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

or on macOS/Linux:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The FastAPI app will run on:
- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

### Start the frontend

In a new terminal:

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

Open the application in your browser at:
- `http://localhost:5173`

## Typical workflow

1. Start the backend API
2. Start the frontend app
3. Upload a PDF, PPTX, or video file from the UI
4. Ask a study question or generate a quiz
5. Review the dashboard and learning insights

## Notes

- The backend stores local application data in `backend/study_companion.db`
- Chroma vector data is stored under `backend/chroma_db/`
- Uploaded materials and generated assets are kept in the backend project folders
- Some AI features may require a working internet connection and valid API credentials

## Troubleshooting

- If the frontend cannot connect to the backend, confirm that `VITE_API_BASE_URL` matches the backend URL and port
- If the backend fails to start, verify Python dependencies were installed and the `.env` file contains valid API keys
- If model downloads fail, make sure you have enough disk space and network access for the embedding and speech models

## License

This project is provided as a local development project. Add your preferred license if you intend to distribute or publish it.
