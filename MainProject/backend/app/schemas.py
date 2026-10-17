from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

RoleKey = Literal["java_developer", "python_developer", "data_analyst", "web_developer",
                  "software_engineer", "ml_engineer", "custom"]


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class InterviewCreate(BaseModel):
    role: RoleKey
    custom_role: str = Field(default="", max_length=120)
    interview_type: Literal["technical", "hr", "project", "coding", "mixed"] = "technical"
    difficulty: Literal["beginner", "intermediate", "advanced", "adaptive"] = "adaptive"
    duration_minutes: Literal[10, 20, 30, 45] = 20
    num_questions: int = Field(default=8, ge=3, le=25)
    language: Literal["en", "hi"] = "en"
    mode: Literal["text", "voice"] = "text"
    resume_text: str = Field(default="", max_length=20000)
    job_description: str = Field(default="", max_length=20000)
    use_profile_resume: bool = True

    @field_validator("custom_role")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class AnswerIn(BaseModel):
    question_id: int
    answer: str = Field(min_length=1, max_length=8000)
    response_seconds: float = Field(default=0, ge=0, le=36000)
    input_mode: Literal["text", "voice"] = "text"


class QuestionAction(BaseModel):
    question_id: int


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    target_role: str | None = Field(default=None, max_length=120)
    experience_level: str | None = Field(default=None, max_length=40)
    preferred_language: Literal["en", "hi"] | None = None
    resume_text: str | None = Field(default=None, max_length=20000)


class ConsentIn(BaseModel):
    training_consent: bool


class RecommendationUpdate(BaseModel):
    status: Literal["open", "done"]
