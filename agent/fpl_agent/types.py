from pydantic import BaseModel, Field

class Player(BaseModel):
    first_name:str
    second_name:str
    price:float
    player_id:int = Field(alias="id")