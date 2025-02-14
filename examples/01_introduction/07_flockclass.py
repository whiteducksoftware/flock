# example.py
from flock.core.flock_class import flockclass, hydrate_object  # adjust import as needed
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter

MODEL = "openai/gpt-4o"

class LongContent:
    title: str
    content: str

class MyBlogPost:
    title: str
    headers: str
    content: dict[str,LongContent]
    # Note: No decorator here; MyBlogPost is treated as a subobject.

@flockclass(MODEL)
class MyProjectPlan:
    project_idea: str
    budget: int
    title: str
    content: MyBlogPost  # This field will be generated via its own agent

if __name__ == "__main__":
    plan = MyProjectPlan()  # note: we don't pass anything
    # Let's give partial fields:
    plan.project_idea = "a declarative agent framework"
    plan.budget = 100000
    # We haven't set plan.title, or plan.content, etc.

    # Now we call our universal hydrator:
    hydrate_object(plan, model="gpt-4")

    # Check the results:
    print("\n--- MyProjectPlan hydrated ---")
    for k, v in plan.__dict__.items():
        print(k, "=", v)

    # If plan.content is a MyBlogPost, let's see what's inside
    if plan.content:
        print("\n--- MyBlogPost hydrated ---")
        for k, v in plan.content.__dict__.items():
            print(k, "=", v)
            if k == "content" and isinstance(v, dict):
                print("\n--- MyBlogPost.content items (LongContent) ---")
                for sub_k, sub_val in v.items():
                    print(sub_k, "->", sub_val)
                    if isinstance(sub_val, LongContent):
                        print("   -> LongContent fields:", sub_val.__dict__)