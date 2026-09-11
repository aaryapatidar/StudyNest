# System Architecture

```mermaid
flowchart LR
  Browser[React frontend] -->|JSON / JWT| API[FastAPI REST API]
  API --> ORM[SQLAlchemy data layer]
  ORM --> DB[(PostgreSQL)]
  API --> Docs[OpenAPI / Swagger]
```
