from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app import services
from app.config import APP_PREVIEW_FILE, FRONTEND_FILE
from app.database import init_db
from app.dependencies import get_current_user
from app.models import (
    DailyCheckinCreate,
    GoalCreate,
    GoalUpdate,
    PlanSuggestionRequest,
    RoutineStepCreate,
    RoutineStepUpdate,
    UserLogin,
    UserRegister,
)

app = FastAPI(
    title="Anchor Backend API",
    version="2.0.0",
    description="Backend base para autenticacion, metas, rutinas y seguimiento diario.",
)

init_db()

# esto es pa q el html local si pueda hablar con la api :v
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _html_page(path, *, missing_message: str, missing_hint: str):
    if path.exists():
        return HTMLResponse(path.read_text(encoding="utf-8"))
    return {
        "message": missing_message,
        "hint": missing_hint,
    }


@app.get("/", include_in_schema=False)
def frontend_home():
    return _html_page(
        FRONTEND_FILE,
        missing_message="Anchor web no encontrada, pero la API esta arriba.",
        missing_hint="Revisa FRONTEND_FILE o sube PRI.html junto al backend.",
    )


@app.get("/app", include_in_schema=False)
def app_preview():
    # TODO Flutter: esta preview web luego sirve de base pa la app mobile real
    return _html_page(
        APP_PREVIEW_FILE,
        missing_message="Anchor app preview no encontrada.",
        missing_hint="Revisa APP_PREVIEW_FILE o sube anchor-app.html junto al backend.",
    )


@app.get("/health")
def home():
    return {
        "message": "Anchor API en ejecucion.",
        "modules": ["auth", "goals", "routine_steps", "checkins", "suggestions"],
    }


@app.get("/app-config")
def app_config():
    return services.get_app_config_service()


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(user: UserRegister):
    return services.register_user(user)


@app.post("/register", include_in_schema=False, status_code=status.HTTP_201_CREATED)
def legacy_register(user: UserRegister):
    return services.register_user(user)


@app.post("/auth/login")
def login(user: UserLogin):
    return services.login_user(user)


@app.post("/login", include_in_schema=False)
def legacy_login(user: UserLogin):
    return services.login_user(user)


@app.get("/users")
def list_users(current_user: dict = Depends(get_current_user)):
    return services.list_users_service()


@app.get("/users/me")
def get_my_profile(current_user: dict = Depends(get_current_user)):
    return {"user": services.serialize_user(current_user)}


@app.post("/plans/suggest")
def suggest_plan(payload: PlanSuggestionRequest):
    return services.suggest_plan(payload.goal_text)


@app.post("/goals", status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    current_user: dict = Depends(get_current_user),
):
    return services.create_goal_service(current_user["id"], payload)


@app.get("/goals")
def list_goals(current_user: dict = Depends(get_current_user)):
    return services.list_goals_service(current_user["id"])


@app.get("/goals/{goal_id}")
def get_goal(goal_id: int, current_user: dict = Depends(get_current_user)):
    return services.get_goal_detail_service(current_user["id"], goal_id)


@app.patch("/goals/{goal_id}")
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    current_user: dict = Depends(get_current_user),
):
    return services.update_goal_service(current_user["id"], goal_id, payload)


@app.post("/goals/{goal_id}/steps", status_code=status.HTTP_201_CREATED)
def create_step(
    goal_id: int,
    payload: RoutineStepCreate,
    current_user: dict = Depends(get_current_user),
):
    return services.create_routine_step_service(current_user["id"], goal_id, payload)


@app.get("/goals/{goal_id}/steps")
def list_steps(goal_id: int, current_user: dict = Depends(get_current_user)):
    return services.list_routine_steps_service(current_user["id"], goal_id)


@app.patch("/goals/{goal_id}/steps/{step_id}")
def update_step(
    goal_id: int,
    step_id: int,
    payload: RoutineStepUpdate,
    current_user: dict = Depends(get_current_user),
):
    return services.update_routine_step_service(
        current_user["id"], goal_id, step_id, payload
    )


@app.post("/goals/{goal_id}/checkins")
def create_checkin(
    goal_id: int,
    payload: DailyCheckinCreate,
    current_user: dict = Depends(get_current_user),
):
    return services.register_checkin_service(current_user["id"], goal_id, payload)


@app.get("/goals/{goal_id}/checkins")
def list_checkins(goal_id: int, current_user: dict = Depends(get_current_user)):
    return services.list_goal_checkins_service(current_user["id"], goal_id)
