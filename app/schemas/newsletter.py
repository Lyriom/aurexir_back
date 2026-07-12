from pydantic import BaseModel, EmailStr, Field


class NewsletterIn(BaseModel):
    email: EmailStr
    locale: str = Field(default="en", pattern=r"^[a-z]{2}$")
