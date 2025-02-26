from typing import Any

from pydantic import Field

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.mixin.prompt_parser import PromptParserMixin
from flock.modules.zep.zep_module import ZepModule, ZepModuleConfig


class ZepEvaluatorConfig(FlockEvaluatorConfig):
    zep_url: str = "http://localhost:8000"
    zep_api_key: str = "apikey"
    min_fact_rating: float = Field(
        default=0.7, description="Minimum rating for facts to be considered"
    )


class ZepEvaluator(FlockEvaluator, DSPyIntegrationMixin, PromptParserMixin):
    """Evaluator that uses DSPy for generation."""

    config: ZepEvaluatorConfig = Field(
        default_factory=ZepEvaluatorConfig,
        description="Evaluator configuration",
    )

    async def evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any], tools: list[Any]
    ) -> dict[str, Any]:
        """Simple evaluator that uses Zep.

        if inputs contain "query", it searches memory for the query and returns the facts.
        if inputs contain "data", it adds the data to memory
        """
        result = {}
        zep = ZepModule(
            name=self.name,
            config=ZepModuleConfig(
                zep_api_key=self.config.zep_api_key,
                zep_url=self.config.zep_url,
                min_fact_rating=self.config.min_fact_rating,
                enable_read=True,
                enable_write=True,
            ),
        )
        client = zep.get_client()
        if "query" in inputs:
            query = inputs["query"]
            facts = zep.search_memory(query, client)
            result = {"facts": facts}

        if "data" in inputs:
            data = inputs["data"]
            zep.add_to_memory(data, client)
            result = {"message": "Data added to memory"}
        return result
