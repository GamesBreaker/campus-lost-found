from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UserOut(BaseModel):
    id: int
    username: str


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9_\u4e00-\u9fff]{3,20}", value):
            raise ValueError("用户名只能包含中文、字母、数字和下划线，长度 3-20 位")
        return value

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码至少 8 个字符")
        if len(value) > 128:
            raise ValueError("密码不能超过 128 个字符")
        return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        return value.strip()


class ReportCreate(BaseModel):
    kind: Literal["lost", "found"]
    description: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=100)
    happened_at: str | None = Field(default=None, max_length=100)
    contact: str = Field(min_length=1, max_length=120)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请描述丢失或捡到的物品")
        return value

    @field_validator("location", "happened_at")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("contact")
    @classmethod
    def clean_contact(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请填写联系方式")
        return value


class BoardPost(BaseModel):
    id: int
    kind: Literal["lost", "found"]
    description: str
    location: str | None
    happened_at: str | None
    username: str
    is_mine: bool


class MatchItem(BaseModel):
    id: int
    similarity: float
    own_username: str
    own_contact: str
    other_username: str
    other_contact: str
    other_kind: Literal["lost", "found"]
    other_description: str
    other_location: str | None
    other_happened_at: str | None


class MatchGroup(BaseModel):
    report: BoardPost
    matches: list[MatchItem]


class HomeResponse(BaseModel):
    authenticated: bool
    user: UserOut | None = None
    lost_posts: list[BoardPost]
    found_posts: list[BoardPost]
    match_groups: list[MatchGroup]


class CompleteResponse(BaseModel):
    deleted_report_ids: list[int]



class ReportSubmitResponse(BaseModel):
    report_id: int
    match_count: int


class MessageResponse(BaseModel):
    ok: bool

