# Nexus

> Topluluk odaklı, REST API tabanlı bir forum/Q&A platformu (Reddit klonu).

## Teknoloji Yığını

- **Backend:** Python, Django, Django REST Framework, SimpleJWT
- **Veritabanı:** PostgreSQL
- **Frontend:** React (Vite, TypeScript), React Router, Redux Toolkit, TailwindCSS

## Dokümantasyon

- [.docs/ARCHITECTURE.md](./.docs/ARCHITECTURE.md) — Mimari, ER modeli, klasör yapısı, API konvansiyonları
- [.docs/PROGRESS.md](./.docs/PROGRESS.md) — Geliştirme yol haritası (fazlı, checkbox'lı)

## Geliştirme

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # değerleri doldur
python manage.py migrate
python manage.py runserver

# Frontend
cd frontend
npm install
cp .env.example .env  # değerleri doldur
npm run dev
```

## Lisans

MIT
