from .models import Report

from langchain_openai.chat_models import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate

class ReportGenerator:
    def __init__(self):
        parser = PydanticOutputParser(pydantic_object=Report)
        llm = ChatOpenAI()
        prompt = PromptTemplate(
            template="{task_instructions}\n\n{format_instructions}",
            input_variables=["query"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        self.chain = prompt | llm | parser
    
    def run(self, task_prompt)->Report:
        return self.chain.invoke({"task_instructions": task_prompt})