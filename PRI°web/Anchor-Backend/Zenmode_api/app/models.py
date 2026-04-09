from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from app.config import (
    CHECKIN_NOTE_MAX_LENGTH,
    GOAL_DESCRIPTION_MAX_LENGTH,
    GOAL_TITLE_MAX_LENGTH,
    STEP_TITLE_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
)


class UserRegister(BaseModel):
    username: str = Field(
        ...,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
    )
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str = Field(
        ...,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
    )
    password: str = Field(..., min_length=8, max_length=128)


class GoalCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=GOAL_TITLE_MAX_LENGTH)
    description: str = Field(default="", max_length=GOAL_DESCRIPTION_MAX_LENGTH)
    category: str = Field(default="general", max_length=30)
    target_note: str = Field(default="", max_length=120)


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=GOAL_TITLE_MAX_LENGTH,
    )
    description: Optional[str] = Field(
        default=None,
        max_length=GOAL_DESCRIPTION_MAX_LENGTH,
    )
    category: Optional[str] = Field(default=None, max_length=30)
    target_note: Optional[str] = Field(default=None, max_length=120)
    status: Optional[str] = Field(default=None, max_length=20)


class RoutineStepCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=STEP_TITLE_MAX_LENGTH)
    scheduled_time: Optional[str] = Field(default=None, max_length=5)
    step_order: int = Field(..., ge=1, le=20)


class RoutineStepUpdate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=STEP_TITLE_MAX_LENGTH,
    )
    scheduled_time: Optional[str] = Field(default=None, max_length=5)
    step_order: Optional[int] = Field(default=None, ge=1, le=20)


class DailyCheckinCreate(BaseModel):
    checkin_date: Optional[date] = None
    completed_step_ids: List[int] = Field(default_factory=list)
    note: str = Field(default="", max_length=CHECKIN_NOTE_MAX_LENGTH)


class PlanSuggestionRequest(BaseModel):
    goal_text: str = Field(..., min_length=3, max_length=200)
