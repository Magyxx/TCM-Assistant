from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class EchoRequest(BaseModel):
    message: str = Field(min_length=1, max_length=200)


class EchoResponse(BaseModel):
    message: str
    length: int


app = FastAPI(title="Obsidian FastAPI Sandbox", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/echo", response_model=EchoResponse)
def echo(payload: EchoRequest) -> EchoResponse:
    return EchoResponse(message=payload.message, length=len(payload.message))
