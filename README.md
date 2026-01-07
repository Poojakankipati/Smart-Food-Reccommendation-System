# Smart-Food-Reccommendation-System
An AI-based food recommendation system that suggests personalized food items based on user preferences, mood, and budget for smarter restaurant and canteen ordering.
# foodreco — Backend

This project uses a small Flask backend serving the existing frontend templates.

Quick start (Windows):

1. Create and activate a virtual environment

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

3. Initialize the database (creates `foodreco.db` and a default admin)

```bash
python backend/init_db.py
```

Default admin credentials: mobile `7671953326` (or `+917671953326`), password `adminpass`.

4. Run the app

```bash
python backend/app.py
```

Open http://127.0.0.1:5000/ to access the login page.
