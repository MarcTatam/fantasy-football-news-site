from pydantic import BaseModel, Field

class Report(BaseModel):
    headline:str = Field(description="The headline of the report")
    body:str = Field(description="The body of the report")