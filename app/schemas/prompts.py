from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PromptKind = Literal["TEXT", "STRUCTURED", "IMAGE", "VIDEO", "AUDIO"]
PromptOutputType = Literal["text", "image", "video", "sound"]
PromptOutputFormat = Literal["text", "structured_json", "structured_yaml"]


class PromptVariable(BaseModel):
    name: str
    default_value: str | None = None
    required: bool


class PromptSearchResult(BaseModel):
    id: str
    title: str
    description: str
    author_name: str
    prompt_type: PromptKind
    category: str
    tags: list[str]
    link: str
    has_variables: bool


class PromptDetail(PromptSearchResult):
    template: str
    variables: list[PromptVariable] = Field(default_factory=list)


class PromptImproveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str = Field(min_length=3, max_length=8000)
    output_type: PromptOutputType = Field(default="text", alias="outputType")
    output_format: PromptOutputFormat = Field(default="text", alias="outputFormat")


class PromptImproveResponse(BaseModel):
    improved_prompt: str
    changes: list[str] = Field(default_factory=list)
