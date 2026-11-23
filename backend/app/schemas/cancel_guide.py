from pydantic import BaseModel


class CancelGuideResponse(BaseModel):
    merchant_key: str
    name: str
    url: str
    difficulty: str
    steps: list[str]
    known: bool
