# API Documentation

FastAPI exposes interactive documentation at `/docs` and ReDoc at `/redoc`. Authentication uses a bearer JWT obtained from `POST /api/auth/login`.

| Group | Routes |
|---|---|
| Auth | register, login, me |
| Subjects | list, create, get, update, delete |
| Notes | list/search, create, update, delete |
| Tasks | list, create, update, delete |
| Resources | list, create |
| Reporting | dashboard, progress, notifications |
