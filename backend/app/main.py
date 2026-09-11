from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./studynest.db"
    secret_key: str = "development-only-change-me"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    access_token_expire_minutes: int = 60 * 24
    environment: str = "development"


settings = Settings()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    college: Mapped[str] = mapped_column(String(150))
    course: Mapped[str] = mapped_column(String(100))
    semester: Mapped[int] = mapped_column(Integer)
    subjects: Mapped[list["SubjectModel"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class SubjectModel(Base):
    __tablename__ = "subjects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100)); code: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(500), default=""); semester: Mapped[int] = mapped_column(Integer)
    owner: Mapped[UserModel] = relationship(back_populates="subjects")


class NoteModel(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True); user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True); title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default=""); tags: Mapped[str] = mapped_column(Text, default="")
    favorite: Mapped[bool] = mapped_column(Boolean, default=False); archived: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TaskModel(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True); user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id"), nullable=True); title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default=""); due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="Medium"); task_type: Mapped[str] = mapped_column(String(100), default="Personal study task")
    status: Mapped[str] = mapped_column(String(20), default="Pending")


class ResourceModel(Base):
    __tablename__ = "resources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True); user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id"), nullable=True); title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500)); description: Mapped[str] = mapped_column(Text, default=""); resource_type: Mapped[str] = mapped_column(String(50), default="Website")


class RevisionModel(Base):
    __tablename__ = "revision_topics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True); user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id"), nullable=True); topic: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="Needs Revision"); next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class User(BaseModel):
    id: UUID; full_name: str; email: EmailStr; college: str; course: str; semester: int

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100); email: EmailStr; password: str = Field(min_length=8, max_length=72)
    college: str = Field(min_length=2, max_length=150); course: str = Field(min_length=2, max_length=100); semester: int = Field(ge=1, le=12)

class Token(BaseModel):
    access_token: str; token_type: str = "bearer"

class SubjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100); code: str = Field(min_length=2, max_length=20); description: str = Field(default="", max_length=500); semester: int = Field(ge=1, le=12)
class Subject(SubjectCreate):
    id: UUID; notes_count: int = 0; tasks_count: int = 0; progress: int = Field(default=0, ge=0, le=100)

class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200); content: str = ""; subject_id: UUID; tags: list[str] = Field(default_factory=list); favorite: bool = False; archived: bool = False
class Note(NoteCreate):
    id: UUID; updated_at: datetime

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200); description: str = ""; subject_id: UUID | None = None; due_date: datetime | None = None
    priority: str = Field(default="Medium", pattern="^(Low|Medium|High)$"); task_type: str = Field(default="Personal study task", max_length=100); status: str = Field(default="Pending", pattern="^(Pending|In Progress|Completed)$")
class Task(TaskCreate):
    id: UUID

class ResourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200); url: str = Field(min_length=5, max_length=500); subject_id: UUID | None = None; description: str = ""; resource_type: str = Field(default="Website", max_length=50)
class Resource(ResourceCreate):
    id: UUID

class RevisionCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=200); subject_id: UUID | None = None; status: str = Field(default="Needs Revision", pattern="^(Needs Revision|Reviewed|Mastered)$"); next_review_at: datetime | None = None
class Revision(RevisionCreate):
    id: UUID


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DbDep = Annotated[Session, Depends(get_db)]


def user_out(x):
    return User(id=UUID(x.id), full_name=x.full_name, email=x.email, college=x.college, course=x.course, semester=x.semester)

def note_out(x):
    return Note(id=UUID(x.id), title=x.title, content=x.content, subject_id=UUID(x.subject_id), tags=[v for v in x.tags.split(",") if v], favorite=x.favorite, archived=x.archived, updated_at=x.updated_at)

def task_out(x):
    return Task(id=UUID(x.id), title=x.title, description=x.description, subject_id=UUID(x.subject_id) if x.subject_id else None, due_date=x.due_date, priority=x.priority, task_type=x.task_type, status=x.status)

def resource_out(x):
    return Resource(id=UUID(x.id), title=x.title, url=x.url, subject_id=UUID(x.subject_id) if x.subject_id else None, description=x.description, resource_type=x.resource_type)

def revision_out(x):
    return Revision(id=UUID(x.id), topic=x.topic, subject_id=UUID(x.subject_id) if x.subject_id else None, status=x.status, next_review_at=x.next_review_at)

def subject_out(x, db):
    notes = db.scalar(select(func.count()).select_from(NoteModel).where(NoteModel.subject_id == x.id)) or 0
    tasks = db.scalar(select(func.count()).select_from(TaskModel).where(TaskModel.subject_id == x.id)) or 0
    done = db.scalar(select(func.count()).select_from(TaskModel).where(TaskModel.subject_id == x.id, TaskModel.status == "Completed")) or 0
    return Subject(id=UUID(x.id), name=x.name, code=x.code, description=x.description, semester=x.semester, notes_count=notes, tasks_count=tasks, progress=round(done / (notes + tasks) * 100) if notes + tasks else 0)


def create_token(email):
    return jwt.encode({"sub": email, "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)}, settings.secret_key, algorithm="HS256")


def owned_or_404(db, model, item_id, user_id):
    item = db.scalar(select(model).where(model.id == str(item_id), model.user_id == user_id))
    if not item:
        raise HTTPException(404, "Item not found")
    return item


def subject_id_or_404(db, subject_id, user_id):
    if subject_id is None:
        return None
    owned_or_404(db, SubjectModel, subject_id, user_id)
    return str(subject_id)


def current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbDep):
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        email = jwt.decode(token, settings.secret_key, algorithms=["HS256"]).get("sub")
    except JWTError as exc:
        raise error from exc
    user = db.scalar(select(UserModel).where(UserModel.email == email)) if email else None
    if not user:
        raise error
    return user

UserDep = Annotated[UserModel, Depends(current_user)]


def ensure_demo_user():
    """Create tables (if needed) and seed the demo student account."""
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(UserModel).where(UserModel.email == "student@studynest.edu")):
            db.add(UserModel(
                id=str(uuid4()),
                full_name="Pramod Patidar",
                email="student@studynest.edu",
                password_hash=pwd_context.hash("Student@123"),
                college="University of Kerala",
                course="M.Sc. Computer Science",
                semester=4,
            ))
            db.commit()


# Create tables eagerly so TestClient (which may skip lifespan) and
# plain imports still have a usable SQLite DB. Lifespan re-runs this
# safely (idempotent) for production startup checks + seeding.
ensure_demo_user()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment.lower() == "production" and (settings.secret_key == "development-only-change-me" or len(settings.secret_key) < 32):
        raise RuntimeError("SECRET_KEY must be a unique value of at least 32 characters in production")
    ensure_demo_user()
    yield


app = FastAPI(title="StudyNest API", version="1.1.0", description="Persistent, user-scoped student study management API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])


@app.get("/api/health")
def health(db: DbDep):
    db.execute(select(1))
    return {"status": "ok", "service": "studynest-api"}


@app.post("/api/auth/register", response_model=User, status_code=201)
def register(p: RegisterRequest, db: DbDep):
    email = str(p.email).lower()
    if db.scalar(select(UserModel).where(UserModel.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    x = UserModel(id=str(uuid4()), full_name=p.full_name, email=email, password_hash=pwd_context.hash(p.password), college=p.college, course=p.course, semester=p.semester)
    db.add(x)
    db.commit()
    return user_out(x)


@app.post("/api/auth/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbDep):
    x = db.scalar(select(UserModel).where(UserModel.email == form.username.lower()))
    if not x or not pwd_context.verify(form.password, x.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return Token(access_token=create_token(x.email))


@app.get("/api/auth/me", response_model=User)
def me(user: UserDep):
    return user_out(user)


@app.get("/api/subjects", response_model=list[Subject])
def list_subjects(user: UserDep, db: DbDep, search: str | None = None, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)):
    q = select(SubjectModel).where(SubjectModel.user_id == user.id).order_by(SubjectModel.name)
    if search:
        q = q.where(func.lower(SubjectModel.name).like(f"%{search.lower()}%") | func.lower(SubjectModel.code).like(f"%{search.lower()}%"))
    return [subject_out(x, db) for x in db.scalars(q.offset((page - 1) * limit).limit(limit))]


@app.post("/api/subjects", response_model=Subject, status_code=201)
def create_subject(p: SubjectCreate, user: UserDep, db: DbDep):
    x = SubjectModel(id=str(uuid4()), user_id=user.id, **p.model_dump())
    db.add(x)
    db.commit()
    return subject_out(x, db)


@app.get("/api/subjects/{item_id}", response_model=Subject)
def get_subject(item_id: UUID, user: UserDep, db: DbDep):
    return subject_out(owned_or_404(db, SubjectModel, item_id, user.id), db)


@app.put("/api/subjects/{item_id}", response_model=Subject)
def update_subject(item_id: UUID, p: SubjectCreate, user: UserDep, db: DbDep):
    x = owned_or_404(db, SubjectModel, item_id, user.id)
    for key, value in p.model_dump().items():
        setattr(x, key, value)
    db.commit()
    return subject_out(x, db)


@app.delete("/api/subjects/{item_id}", status_code=204)
def delete_subject(item_id: UUID, user: UserDep, db: DbDep):
    x = owned_or_404(db, SubjectModel, item_id, user.id)
    refs = (db.scalar(select(func.count()).select_from(NoteModel).where(NoteModel.subject_id == x.id)) or 0) + (db.scalar(select(func.count()).select_from(TaskModel).where(TaskModel.subject_id == x.id)) or 0)
    if refs:
        raise HTTPException(409, "Delete or reassign this subject's notes and tasks first")
    db.delete(x)
    db.commit()


@app.get("/api/notes", response_model=list[Note])
def list_notes(user: UserDep, db: DbDep, search: str | None = None, subject_id: UUID | None = None, favorite: bool | None = None):
    q = select(NoteModel).where(NoteModel.user_id == user.id)
    if search:
        q = q.where(func.lower(NoteModel.title + " " + NoteModel.content + " " + NoteModel.tags).like(f"%{search.lower()}%"))
    if subject_id:
        q = q.where(NoteModel.subject_id == str(subject_id))
    if favorite is not None:
        q = q.where(NoteModel.favorite == favorite)
    return [note_out(x) for x in db.scalars(q.order_by(NoteModel.updated_at.desc()))]


@app.post("/api/notes", response_model=Note, status_code=201)
def create_note(p: NoteCreate, user: UserDep, db: DbDep):
    x = NoteModel(id=str(uuid4()), user_id=user.id, subject_id=subject_id_or_404(db, p.subject_id, user.id), title=p.title, content=p.content, tags=",".join(v.strip() for v in p.tags if v.strip()), favorite=p.favorite, archived=p.archived)
    db.add(x)
    db.commit()
    return note_out(x)


@app.get("/api/notes/{item_id}", response_model=Note)
def get_note(item_id: UUID, user: UserDep, db: DbDep):
    return note_out(owned_or_404(db, NoteModel, item_id, user.id))


@app.put("/api/notes/{item_id}", response_model=Note)
def update_note(item_id: UUID, p: NoteCreate, user: UserDep, db: DbDep):
    x = owned_or_404(db, NoteModel, item_id, user.id)
    x.subject_id = subject_id_or_404(db, p.subject_id, user.id)
    x.title = p.title
    x.content = p.content
    x.tags = ",".join(v.strip() for v in p.tags if v.strip())
    x.favorite = p.favorite
    x.archived = p.archived
    db.commit()
    return note_out(x)


@app.delete("/api/notes/{item_id}", status_code=204)
def delete_note(item_id: UUID, user: UserDep, db: DbDep):
    db.delete(owned_or_404(db, NoteModel, item_id, user.id))
    db.commit()


def apply_task(x, p, db, user_id):
    x.title = p.title
    x.description = p.description
    x.subject_id = subject_id_or_404(db, p.subject_id, user_id)
    x.due_date = p.due_date
    x.priority = p.priority
    x.task_type = p.task_type
    x.status = p.status


@app.get("/api/tasks", response_model=list[Task])
def list_tasks(user: UserDep, db: DbDep, task_status: str | None = Query(None, alias="status")):
    q = select(TaskModel).where(TaskModel.user_id == user.id)
    if task_status:
        q = q.where(TaskModel.status == task_status)
    return [task_out(x) for x in db.scalars(q.order_by(TaskModel.due_date.is_(None), TaskModel.due_date))]


@app.post("/api/tasks", response_model=Task, status_code=201)
def create_task(p: TaskCreate, user: UserDep, db: DbDep):
    x = TaskModel(id=str(uuid4()), user_id=user.id)
    apply_task(x, p, db, user.id)
    db.add(x)
    db.commit()
    return task_out(x)


@app.get("/api/tasks/{item_id}", response_model=Task)
def get_task(item_id: UUID, user: UserDep, db: DbDep):
    return task_out(owned_or_404(db, TaskModel, item_id, user.id))


@app.put("/api/tasks/{item_id}", response_model=Task)
def update_task(item_id: UUID, p: TaskCreate, user: UserDep, db: DbDep):
    x = owned_or_404(db, TaskModel, item_id, user.id)
    apply_task(x, p, db, user.id)
    db.commit()
    return task_out(x)


@app.delete("/api/tasks/{item_id}", status_code=204)
def delete_task(item_id: UUID, user: UserDep, db: DbDep):
    db.delete(owned_or_404(db, TaskModel, item_id, user.id))
    db.commit()


def apply_resource(x, p, db, user_id):
    x.title = p.title
    x.url = p.url
    x.subject_id = subject_id_or_404(db, p.subject_id, user_id)
    x.description = p.description
    x.resource_type = p.resource_type


@app.get("/api/resources", response_model=list[Resource])
def list_resources(user: UserDep, db: DbDep):
    return [resource_out(x) for x in db.scalars(select(ResourceModel).where(ResourceModel.user_id == user.id).order_by(ResourceModel.title))]


@app.post("/api/resources", response_model=Resource, status_code=201)
def create_resource(p: ResourceCreate, user: UserDep, db: DbDep):
    x = ResourceModel(id=str(uuid4()), user_id=user.id)
    apply_resource(x, p, db, user.id)
    db.add(x)
    db.commit()
    return resource_out(x)


@app.get("/api/resources/{item_id}", response_model=Resource)
def get_resource(item_id: UUID, user: UserDep, db: DbDep):
    return resource_out(owned_or_404(db, ResourceModel, item_id, user.id))


@app.put("/api/resources/{item_id}", response_model=Resource)
def update_resource(item_id: UUID, p: ResourceCreate, user: UserDep, db: DbDep):
    x = owned_or_404(db, ResourceModel, item_id, user.id)
    apply_resource(x, p, db, user.id)
    db.commit()
    return resource_out(x)


@app.delete("/api/resources/{item_id}", status_code=204)
def delete_resource(item_id: UUID, user: UserDep, db: DbDep):
    db.delete(owned_or_404(db, ResourceModel, item_id, user.id))
    db.commit()


def apply_revision(x, p, db, user_id):
    x.topic = p.topic
    x.subject_id = subject_id_or_404(db, p.subject_id, user_id)
    x.status = p.status
    x.next_review_at = p.next_review_at


@app.get("/api/revisions", response_model=list[Revision])
def list_revisions(user: UserDep, db: DbDep):
    return [revision_out(x) for x in db.scalars(select(RevisionModel).where(RevisionModel.user_id == user.id))]


@app.post("/api/revisions", response_model=Revision, status_code=201)
def create_revision(p: RevisionCreate, user: UserDep, db: DbDep):
    x = RevisionModel(id=str(uuid4()), user_id=user.id)
    apply_revision(x, p, db, user.id)
    db.add(x)
    db.commit()
    return revision_out(x)


@app.put("/api/revisions/{item_id}", response_model=Revision)
def update_revision(item_id: UUID, p: RevisionCreate, user: UserDep, db: DbDep):
    x = owned_or_404(db, RevisionModel, item_id, user.id)
    apply_revision(x, p, db, user.id)
    db.commit()
    return revision_out(x)


@app.delete("/api/revisions/{item_id}", status_code=204)
def delete_revision(item_id: UUID, user: UserDep, db: DbDep):
    db.delete(owned_or_404(db, RevisionModel, item_id, user.id))
    db.commit()


@app.get("/api/dashboard")
def dashboard(user: UserDep, db: DbDep):
    count = lambda model, *conditions: db.scalar(select(func.count()).select_from(model).where(model.user_id == user.id, *conditions)) or 0
    return {
        "subjects": count(SubjectModel),
        "notes": count(NoteModel),
        "pending_tasks": count(TaskModel, TaskModel.status != "Completed"),
        "completed_tasks": count(TaskModel, TaskModel.status == "Completed"),
    }


@app.get("/api/progress")
def progress(user: UserDep, db: DbDep):
    total = db.scalar(select(func.count()).select_from(TaskModel).where(TaskModel.user_id == user.id)) or 0
    done = db.scalar(select(func.count()).select_from(TaskModel).where(TaskModel.user_id == user.id, TaskModel.status == "Completed")) or 0
    revisions = list(db.scalars(select(RevisionModel).where(RevisionModel.user_id == user.id)))
    return {
        "subjects_completed": 0,
        "notes_created": db.scalar(select(func.count()).select_from(NoteModel).where(NoteModel.user_id == user.id)) or 0,
        "tasks_completed": done,
        "task_completion_rate": round(done / total * 100) if total else 0,
        "revision_completed": round(sum(x.status == "Mastered" for x in revisions) / len(revisions) * 100) if revisions else 0,
        "weekly_tasks": [0] * 7,
    }


@app.get("/api/notifications")
def notifications(user: UserDep, db: DbDep):
    due = list(db.scalars(select(TaskModel).where(
        TaskModel.user_id == user.id,
        TaskModel.status != "Completed",
        TaskModel.due_date.is_not(None),
        TaskModel.due_date <= datetime.now(timezone.utc) + timedelta(days=1),
    )))
    return [{"id": x.id, "message": f"{x.title} is due soon.", "read": False} for x in due]
