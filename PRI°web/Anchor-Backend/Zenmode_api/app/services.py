import json
import re
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status

from app import database
from app.auth import (
    PASSWORD_POLICY_HINT,
    create_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.config import (
    ALLOWED_GOAL_CATEGORIES,
    ALLOWED_GOAL_STATUSES,
    APP_NAME,
    DEMO_MODE,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    LLM_TIMEOUT_SECONDS,
)

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

PLAN_TEMPLATES = {
    "study": {
        "title": "Plan para estudiar con menos distraccion",
        "steps": [
            "Define una sola materia o tema para la sesion.",
            "Bloquea 45 minutos sin redes ni video corto.",
            "Haz una pausa de 10 minutos y vuelve otros 35.",
            "Cierra con una mini revision de lo que si entendiste.",
        ],
    },
    "sleep": {
        "title": "Plan para dormir mejor",
        "steps": [
            "Activa el modo descanso 45 minutos antes de dormir.",
            "Deja el celular fuera de la cama o fuera del cuarto.",
            "Haz una actividad corta de cierre: lectura o respiracion.",
            "Repite la misma hora de sueno por varios dias.",
        ],
    },
    "exercise": {
        "title": "Plan para volver al ejercicio",
        "steps": [
            "Empieza con una rutina breve de 20 a 30 minutos.",
            "Define una hora fija y preparala con anticipacion.",
            "Evita pantallas justo antes de entrenar.",
            "Marca el dia como cumplido aunque haya sido corto.",
        ],
    },
    "reading": {
        "title": "Plan para leer de nuevo",
        "steps": [
            "Pon una meta pequena: 10 o 15 paginas.",
            "Asocia la lectura a un momento fijo del dia.",
            "Silencia notificaciones mientras lees.",
            "Cierra anotando una idea o frase clave.",
        ],
    },
    "general": {
        "title": "Plan base para convertir una meta en rutina",
        "steps": [
            "Aclara que quieres lograr y en cuanto tiempo.",
            "Parte la meta en acciones pequenas y diarias.",
            "Quita un distractor claro del entorno.",
            "Revisa al final del dia si cumpliste o no.",
        ],
    },
}


def _model_dump(model: Any, *, exclude_unset: bool = False) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=exclude_unset)
    return model.dict(exclude_unset=exclude_unset)


def _clean_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def _normalize_username(username: str) -> str:
    normalized = _clean_text(username).lower()

    if not USERNAME_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El username solo puede tener letras, numeros, punto, guion "
                "y guion bajo."
            ),
        )

    return normalized


def _validate_password(password: str) -> None:
    issues = validate_password_strength(password)

    if issues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": PASSWORD_POLICY_HINT, "issues": issues},
        )


def _normalize_goal_category(category: str) -> str:
    normalized = _clean_text(category).lower() or "general"

    if normalized not in ALLOWED_GOAL_CATEGORIES:
        valid_categories = ", ".join(sorted(ALLOWED_GOAL_CATEGORIES))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categoria invalida. Usa una de: {valid_categories}.",
        )

    return normalized


def _normalize_goal_status(goal_status: str) -> str:
    normalized = _clean_text(goal_status).lower()

    if normalized not in ALLOWED_GOAL_STATUSES:
        valid_statuses = ", ".join(sorted(ALLOWED_GOAL_STATUSES))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado invalido. Usa uno de: {valid_statuses}.",
        )

    return normalized


def _normalize_step_time(value: Optional[str]) -> Optional[str]:
    normalized = _clean_text(value or "")
    if not normalized:
        return None

    if not TIME_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La hora debe tener formato HH:MM.",
        )

    return normalized


def _normalize_checkin_date(value: Optional[date]) -> str:
    current_date = value or date.today()

    if current_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes registrar seguimiento en fechas futuras.",
        )

    return current_date.isoformat()


def _require_goal_for_user(user_id: int, goal_id: int) -> Dict[str, Any]:
    goal = database.get_goal_by_id_for_user(goal_id, user_id)

    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meta no encontrada para este usuario.",
        )

    return goal


def _require_step_for_goal(goal_id: int, step_id: int) -> Dict[str, Any]:
    step = database.get_step_by_id(goal_id, step_id)

    if step is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paso no encontrado.",
        )

    return step


def _calculate_streak(checkins: List[Dict[str, Any]]) -> int:
    successful_dates = sorted(
        (
            date.fromisoformat(item["checkin_date"])
            for item in checkins
            if item["status"] == "done"
        ),
        reverse=True,
    )

    if not successful_dates:
        return 0

    streak = 1
    previous_date = successful_dates[0]

    for current_date in successful_dates[1:]:
        if previous_date - current_date == timedelta(days=1):
            streak += 1
            previous_date = current_date
            continue
        break

    return streak


def _build_goal_stats(
    steps: List[Dict[str, Any]],
    checkins: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total_checkins = len(checkins)
    average_completion = (
        round(
            sum(item["completion_percent"] for item in checkins) / total_checkins,
            2,
        )
        if total_checkins
        else 0
    )

    return {
        "total_steps": len(steps),
        "total_checkins": total_checkins,
        "completion_rate": average_completion,
        "current_streak": _calculate_streak(checkins),
        "last_checkin_date": checkins[0]["checkin_date"] if checkins else None,
    }


def serialize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "created_at": user.get("created_at"),
    }


def _serialize_goal(
    goal: Dict[str, Any],
    steps: List[Dict[str, Any]],
    checkins: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "id": goal["id"],
        "title": goal["title"],
        "description": goal["description"],
        "category": goal["category"],
        "target_note": goal["target_note"],
        "status": goal["status"],
        "created_at": goal["created_at"],
        "updated_at": goal["updated_at"],
        "routine_steps": steps,
        "recent_checkins": checkins[:7],
        "stats": _build_goal_stats(steps, checkins),
    }


def _detect_goal_category(goal_text: str) -> str:
    lower_goal = goal_text.lower()

    if any(keyword in lower_goal for keyword in ("dorm", "noche", "descans")):
        return "sleep"
    if any(keyword in lower_goal for keyword in ("estudi", "concentr", "tarea")):
        return "study"
    if any(keyword in lower_goal for keyword in ("ejercicio", "entren", "gym")):
        return "exercise"
    if any(keyword in lower_goal for keyword in ("leer", "lectura", "libro")):
        return "reading"
    return "general"


def _build_template_plan(goal_text: str, category: str) -> Dict[str, Any]:
    template = PLAN_TEMPLATES[category]
    return {
        "goal_text": goal_text,
        "category": category,
        "title": template["title"],
        "steps": template["steps"],
        "source": "local",
    }


def _extract_gemini_text(data: Dict[str, Any]) -> str:
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            if part.get("text"):
                return part["text"]

    return ""


def _normalize_ai_plan(goal_text: str, category: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    title = _clean_text(str(payload.get("title", ""))) or PLAN_TEMPLATES[category]["title"]
    raw_steps = payload.get("steps") or []

    if not isinstance(raw_steps, list):
        raw_steps = []

    clean_steps = []
    for item in raw_steps:
        text = _clean_text(str(item))
        if text:
            clean_steps.append(text)

    if len(clean_steps) < 3:
        clean_steps = PLAN_TEMPLATES[category]["steps"]

    return {
        "goal_text": goal_text,
        "category": category,
        "title": title,
        "steps": clean_steps[:6],
        "source": "gemini-free",
    }


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("\n")
        if len(parts) >= 3:
            cleaned = "\n".join(parts[1:-1]).strip()
    return cleaned


def _request_gemini_plan(goal_text: str, category: str) -> Optional[Dict[str, Any]]:
    if not GEMINI_API_KEY:
        return None

    # esto arma el prompt pa q salga corto y en json :D
    prompt = (
        "Eres un asistente de bienestar digital para Anchor. "
        "Devuelve solo JSON valido con las llaves title y steps. "
        "steps debe ser una lista de 4 a 6 pasos cortos en espanol. "
        f"La categoria sugerida es: {category}. "
        f"La meta del usuario es: {goal_text}"
    )

    try:
        response = httpx.post(
            f"{GEMINI_BASE_URL}/{GEMINI_MODEL}:generateContent",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ]
            },
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        text = _extract_gemini_text(response.json())
        if not text:
            return None

        return _normalize_ai_plan(
            goal_text,
            category,
            json.loads(_strip_code_fence(text)),
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def register_user(payload: Any) -> Dict[str, Any]:
    username = _normalize_username(payload.username)
    _validate_password(payload.password)

    if database.get_user_by_username(username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese username ya existe.",
        )

    try:
        user = database.create_user(username, hash_password(payload.password))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo crear el usuario porque ya existe.",
        ) from exc

    return {
        "message": "Usuario registrado con exito.",
        "user": serialize_user(user),
    }


def login_user(payload: Any) -> Dict[str, Any]:
    username = _normalize_username(payload.username)
    user = database.get_user_by_username(username)

    if user is None or not verify_password(payload.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas.",
        )

    token = create_token({"sub": user["username"], "uid": user["id"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }


def list_users_service() -> Dict[str, Any]:
    users = [serialize_user(user) for user in database.list_users()]
    return {"total": len(users), "users": users}


def create_goal_service(user_id: int, payload: Any) -> Dict[str, Any]:
    title = _clean_text(payload.title)
    description = _clean_text(payload.description)
    category = _normalize_goal_category(payload.category)
    target_note = _clean_text(payload.target_note)

    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La meta debe tener un titulo valido.",
        )

    goal = database.create_goal(
        user_id=user_id,
        title=title,
        description=description,
        category=category,
        target_note=target_note,
    )

    return {
        "message": "Meta creada con exito.",
        "goal": _serialize_goal(goal, [], []),
    }


def list_goals_service(user_id: int) -> Dict[str, Any]:
    goals = []

    for goal in database.list_goals_for_user(user_id):
        steps = database.list_steps_for_goal(goal["id"])
        checkins = database.list_checkins_for_goal(goal["id"])
        goals.append(_serialize_goal(goal, steps, checkins))

    return {"total": len(goals), "goals": goals}


def get_goal_detail_service(user_id: int, goal_id: int) -> Dict[str, Any]:
    goal = _require_goal_for_user(user_id, goal_id)
    steps = database.list_steps_for_goal(goal_id)
    checkins = database.list_checkins_for_goal(goal_id)

    return {"goal": _serialize_goal(goal, steps, checkins)}


def update_goal_service(user_id: int, goal_id: int, payload: Any) -> Dict[str, Any]:
    _require_goal_for_user(user_id, goal_id)
    updates = _model_dump(payload, exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enviaste cambios para actualizar la meta.",
        )

    clean_updates: Dict[str, Any] = {}

    if "title" in updates:
        title = _clean_text(updates["title"])
        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El titulo no puede quedar vacio.",
            )
        clean_updates["title"] = title

    if "description" in updates:
        clean_updates["description"] = _clean_text(updates["description"])

    if "category" in updates:
        clean_updates["category"] = _normalize_goal_category(updates["category"])

    if "target_note" in updates:
        clean_updates["target_note"] = _clean_text(updates["target_note"])

    if "status" in updates:
        clean_updates["status"] = _normalize_goal_status(updates["status"])

    database.update_goal(goal_id, user_id, clean_updates)
    return {
        "message": "Meta actualizada con exito.",
        **get_goal_detail_service(user_id, goal_id),
    }


def create_routine_step_service(user_id: int, goal_id: int, payload: Any) -> Dict[str, Any]:
    _require_goal_for_user(user_id, goal_id)

    title = _clean_text(payload.title)
    scheduled_time = _normalize_step_time(payload.scheduled_time)
    step_order = payload.step_order

    if database.get_step_by_order(goal_id, step_order):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un paso con ese orden en esta meta.",
        )

    try:
        step = database.create_routine_step(goal_id, title, scheduled_time, step_order)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo guardar el paso por conflicto de orden.",
        ) from exc

    return {
        "message": "Paso agregado con exito.",
        "step": step,
        **get_goal_detail_service(user_id, goal_id),
    }


def list_routine_steps_service(user_id: int, goal_id: int) -> Dict[str, Any]:
    _require_goal_for_user(user_id, goal_id)
    steps = database.list_steps_for_goal(goal_id)
    return {"total": len(steps), "steps": steps}


def update_routine_step_service(
    user_id: int,
    goal_id: int,
    step_id: int,
    payload: Any,
) -> Dict[str, Any]:
    _require_goal_for_user(user_id, goal_id)
    current_step = _require_step_for_goal(goal_id, step_id)
    updates = _model_dump(payload, exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enviaste cambios para actualizar el paso.",
        )

    clean_updates: Dict[str, Any] = {}

    if "title" in updates:
        title = _clean_text(updates["title"])
        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El titulo del paso no puede quedar vacio.",
            )
        clean_updates["title"] = title

    if "scheduled_time" in updates:
        clean_updates["scheduled_time"] = _normalize_step_time(
            updates["scheduled_time"]
        )

    if "step_order" in updates:
        new_order = updates["step_order"]
        existing_step = database.get_step_by_order(goal_id, new_order)
        if existing_step and existing_step["id"] != current_step["id"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ese orden ya esta ocupado por otro paso.",
            )
        clean_updates["step_order"] = new_order

    try:
        step = database.update_routine_step(goal_id, step_id, clean_updates)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudo actualizar el paso por conflicto de orden.",
        ) from exc

    return {
        "message": "Paso actualizado con exito.",
        "step": step,
        **get_goal_detail_service(user_id, goal_id),
    }


def register_checkin_service(user_id: int, goal_id: int, payload: Any) -> Dict[str, Any]:
    _require_goal_for_user(user_id, goal_id)
    steps = database.list_steps_for_goal(goal_id)

    if not steps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes crear al menos un paso antes de registrar seguimiento.",
        )

    step_ids = {step["id"] for step in steps}
    completed_step_ids = list(dict.fromkeys(payload.completed_step_ids))

    invalid_step_ids = [
        step_id for step_id in completed_step_ids if step_id not in step_ids
    ]
    if invalid_step_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Los pasos {invalid_step_ids} no pertenecen a esta meta.",
        )

    checkin_date = _normalize_checkin_date(payload.checkin_date)
    note = _clean_text(payload.note)
    completion_percent = int(round((len(completed_step_ids) / len(steps)) * 100))

    if completion_percent == 100:
        checkin_status = "done"
    elif completion_percent > 0:
        checkin_status = "partial"
    else:
        checkin_status = "missed"

    checkin = database.upsert_checkin(
        goal_id=goal_id,
        checkin_date=checkin_date,
        completed_step_ids=completed_step_ids,
        note=note,
        status=checkin_status,
        completion_percent=completion_percent,
    )

    return {
        "message": "Seguimiento guardado con exito.",
        "checkin": checkin,
        **get_goal_detail_service(user_id, goal_id),
    }


def list_goal_checkins_service(user_id: int, goal_id: int) -> Dict[str, Any]:
    _require_goal_for_user(user_id, goal_id)
    checkins = database.list_checkins_for_goal(goal_id)
    return {"total": len(checkins), "checkins": checkins}


def suggest_plan(goal_text: str) -> Dict[str, Any]:
    normalized_goal = _clean_text(goal_text)
    category = _detect_goal_category(normalized_goal)

    # esto intenta gemini free tier, si no hay key cae al plan fijo :v
    ai_plan = _request_gemini_plan(normalized_goal, category)
    if ai_plan:
        return ai_plan

    return _build_template_plan(normalized_goal, category)


def get_app_config_service() -> Dict[str, Any]:
    # esto le dice al front si hay ia real o si toca fallback :D
    return {
        "app_name": APP_NAME,
        "ai_enabled": bool(GEMINI_API_KEY),
        "ai_provider": "gemini-free" if GEMINI_API_KEY else "local",
        "demo_mode": DEMO_MODE,
    }
