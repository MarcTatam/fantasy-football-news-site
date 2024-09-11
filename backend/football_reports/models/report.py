class Report(BaseModel):
    headline:str = Field("The headline of the report")
    body:str = Field("The body of the report")