# Multi-language RAG - No problem with flock

from flock.core import Flock, FlockFactory, flock_type
from flock.core.tools.azure_tools import (
    azure_search_query,
    azure_search_get_document
)
from pydantic import BaseModel, Field

# Defining our output model
#
# Being able to declaratively specify requirements for each field is a powerful feature of flock
# and makes prompting much more effective, easier to understand and easier to maintain.
#
# Let's take a look at the RAGResponse model:
# answer - The final answer to the user query.
# max_queries - Flock will retry failed tool calls quite a bit, so the max_queries is a way to limit the number of retries semantically.
# queries - Flock should log the queries used to answer the question.
# error - In case no answer is found after max_queries are used, an error should be returned.
# source_documents - Flock should log the source documents used to answer the question.
# quotes - Flock should log the quotes from the source documents to support the answer.
# 
# As you can see just by simply defining declarative rules for each field,
# we implicitly created a quite complex logical flow that is quite hard to get right with plain prompting.
@flock_type
class RAGResponse(BaseModel):
    answer: str = Field(description="The answer to the user query. Must be concise and to the point.")
    max_queries: int = Field(description="The maximum number of queries used to answer the question")
    queries: list[str] = Field(description="The queries used to answer the question.")
    error: str | None = Field(description="An error message if the answer is not found or the query can't be answered by the context. Must be concise and to the point.")
    source_documents: list[str] = Field(description="The source documents used to answer the question")
    quotes: list[str] = Field(description="A list of quotes from the source documents to support the answer")

MODEL = "openai/gpt-4o"


flock = Flock(name="azure_search_query", model=MODEL)

# Let's take a look at the rag_agent:
#
# Description, input and output are following the same declarative approach as the RAGResponse model.
#
# Let's take a look at those fields:
#
# Description - Not only useful for documentation, but also useful to tell Flock what to do.
# 
# Input - We define the 'question' and 'max_queries' as input and some rules for max_queries.
#
# Output - We define the 'answer' to be of type RAGResponse, which makes all the rules we defined above come into play.
# Also we wrap all those rules into another rule that the answer should be in the same language as the question.
#
# Tools - We define the tools that Flock should use to answer the question.
rag_agent = FlockFactory.create_default_agent(
    name="rag_agent",
    description="Queries Azure Search for facts. The queries should be in the same language as the question. If this produces no results the query can be in english.",
    input="question: str, max_queries: int | Maximum number of allowed queries to use. Return an error if the query can't be answered by the context.",
    output="answer: RAGResponse | The answer should be in the same language as the question.",
    tools=[azure_search_query,azure_search_get_document],
    use_cache=True,
    write_to_file=True
)

flock.add_agent(rag_agent)

flock.run(
    start_agent=rag_agent,
    input={"question": "Wo ist die Turnhalle von Schattdecor?", "max_queries": 2}
    #input={"question": "Wieviele Mitarbeiter hat Schattdecor und wann wurde die Firma gegründet?", "max_queries": 2}
)



