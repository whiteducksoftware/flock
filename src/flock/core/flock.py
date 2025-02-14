from flock.core.flock_class import flockclass
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter

MODEL = "openai/gpt-4"


class LongContent:
    title: str
    content: str


class MyBlogPost:
    title: str
    headers: str
    content: dict[str, LongContent]
    # Note: No decorator here; MyBlogPost is treated as a subobject.


@flockclass(MODEL)
class MyProjectPlan:
    project_idea: str
    budget: int
    title: str
    content: MyBlogPost  # This field will be generated via its own agent


if __name__ == "__main__":
    plan = MyProjectPlan(
        project_idea="a declarative agent framework", budget=100000
    )
    PrettyPrintFormatter().display_data(data=plan.__dict__)
    PrettyPrintFormatter().display_data(data=plan.content.__dict__)
