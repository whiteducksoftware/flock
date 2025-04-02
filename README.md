<p align="center">
<img src="docs/assets/images/flock.png" width="600"><br>
<img alt="Dynamic TOML Badge" src="https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fwhiteducksoftware%2Fflock%2Frefs%2Fheads%2Fmaster%2Fpyproject.toml&query=%24.project.version&style=for-the-badge&logo=pypi&label=pip%20version">
<a href="https://www.linkedin.com/company/whiteduck" target="_blank"><img alt="LinkedIn" src="https://img.shields.io/badge/linkedin-%230077B5.svg?style=for-the-badge&logo=linkedin&logoColor=white&label=whiteduck"></a>
<a href="https://bsky.app/profile/whiteduck-gmbh.bsky.social" target="_blank"><img alt="Bluesky" src="https://img.shields.io/badge/bluesky-Follow-blue?style=for-the-badge&logo=bluesky&logoColor=%23fff&color=%23333&labelColor=%230285FF&label=whiteduck-gmbh"></a>

## Overview

Flock is a framework for orchestrating LLM-powered agents. It leverages a **declarative approach** where you simply specify what each agent needs as input and what it produces as output, without having to write lengthy, brittle prompts. Under the hood, Flock transforms these declarations into robust workflows, using cutting-edge components such as Temporal and DSPy to handle fault tolerance, state management, and error recovery.



| Traditional Agent Frameworks 🙃          |                        Flock 🐤🐧🐓🦆                         |
|------------------------------------------|--------------------------------------------------------------|
| 🤖 **Complex Prompt Engineering**         | 📝 **Declarative Agent Definitions**                         |
| • Lengthy, brittle prompts               | • Clear, concise input/output declarations                   |
| • Hard-to-tune and adapt                 | • No need for manual prompt engineering                      |
|                                          |                                                              |
| 💥 **Fragile Execution**                  | ⚡ **Robust & Scalable**                                      |
| • Single failure can break the system    | • Fault-tolerant with built-in retries and error handling      |
| • Difficult to monitor and recover       | • Automatic recovery via Temporal workflow integration         |
|                                          |                                                              |
| 🏗️ **Rigid Workflows**                    | 🔄 **Flexible Orchestration**                                |
| • Limited adaptability                   | • Dynamic agent chaining and hand-offs                       |
| • Hard to scale and parallelize          | • Modular, concurrent, and batch processing                   |
|                                          |                                                              |

## Video Demonstration


https://github.com/user-attachments/assets/bdab4786-d532-459f-806a-024727164dcc

## Table of Contents

- [Key Innovations](#key-innovations)
- [Examples](#examples)
  - [Hello Flock!](#hello-flock)
  - [It's not my type](#its-not-my-type)
  - [Being pydantic](#being-pydantic)
  - [Building a chain gang!](#building-a-chain-gang)
- [Installation](#installation)


## Key Innovations

- **Declarative Agent System:**  
  When you order a pizza at your favorite place, you just tell them what pizza you want, not the 30 steps to get there!
  And thanks to an invention called LLMs, we now have the technology to come up with those 30 steps.

  Flock takes advantage of that.

  Define agents by declaring their input/output interfaces (with type hints and human-readable descriptions) using a concise syntax.  
  The framework automatically extracts type and description details, builds precise prompts, and configures the underlying LLM.

  Testing becomes quite simple as well. You got the pizza you ordered? Passed ✅

- **Type Safety and Clear Contracts:**  
  Agents are implemented as Pydantic models. This provides automatic JSON serialization/deserialization, strong typing, and an explicit contract for inputs and outputs. Testing, validation, and integration become straightforward.

- **Unparalleled Flexibility:**  
  Each agent (via the new `FlockAgent` base class) supports lifecycle hooks such as `initialize()`, `terminate()`, `evaluate()`, and `on_error()`. This ensures that agents can perform setup, cleanup, and robust error handling—all without cluttering the main business logic. Everything is overridable or lets you provide your own callables per callback. We mean `everything` quite literally. Except for the agent name, literally every property of an agent can be set to a callable, leading to highly dynamic and capable agents.

- **Fault Tolerance & Temporal Integration:**  
  Flock is built with production readiness in mind. By integrating with Temporal, your agent workflows enjoy automatic retries, durable state management, and resilience against failures. This means that a single agent crash won't bring down your entire system.


<p align="center">
<img src="docs/assets/images//flock_cli.png" width="200"><br>

## Examples

Let's showcase easy to understand examples to give you an idea what flock offers!
All examples and/or similar examples can be found in the examples folder!

### Hello Flock!


Let's start the most simple way possible 🚀

```python

from flock.core import Flock, FlockAgent

MODEL = "openai/gpt-4o"

flock = Flock(model=MODEL, local_debug=True)

bloggy = FlockAgent(
    name="bloggy", 
    input="blog_idea", 
    output="funny_blog_title, blog_headers"
)
flock.add_agent(bloggy)

result = flock.run(
    start_agent=bloggy, 
    input={"blog_idea": "A blog about cats"}
)

```

With almost no boilerplate needed, getting your first agent to run is as easy as cake!

`bloggy` takes in a `blog_idea` to produce a `funny_blog_title` and `blog_headers`. That is all!

Flock does take care of the rest, which frees you from needing to write paragraphs of text.
You might think abstracting prompting like this means less control - but nope! Quite the contrary, it'll increase your control over it!

When we let `bloggy` loose in the flock:


```python
{
    'funny_blog_title': '"Whisker Wonders: The Purr-fect Guide to Cat-tastrophes and Feline Follies"',
    'blog_headers': (
        '1. "The Cat\'s Meow: Understanding Your Feline\'s Language"\n'
        '2. "Paws and Reflect: The Secret Life of Cats"\n'
        '3. "Fur Real: Debunking Myths About Our Furry Friends"\n'
        '4. "Claw-some Adventures: How to Entertain Your Indoor Cat"\n'
        '5. "Cat-astrophic Cuteness: Why We Can\'t Resist Those Whiskers"\n'
        '6. "Tail Tales: The History of Cats and Their Human Companions"\n'
        '7. "Purr-sonality Plus: What Your Cat\'s Behavior Says About Them"\n'
        '8. "Kitty Conundrums: Solving Common Cat Problems with Humor"'
    ),
    'blog_idea': 'A blog about cats',
}
```

Look at that! A real Python object with fields exactly as we defined them in the agent.
No need to mess around with parsing or post-processing! 🎉

### It's not my type

You probably noticed that your headers aren't a real Python list, but you need one for your downstream task. Flock got you! Just sprinkle some type hints in your agent definition! ✨

```python

from flock.core import Flock, FlockAgent

MODEL = "openai/gpt-4o"

flock = Flock(model=MODEL, local_debug=True)

bloggy = FlockAgent(
    name="bloggy", 
    input="blog_idea", 
    output="funny_blog_title, blog_headers: list[str]"
)
flock.add_agent(bloggy)

result = flock.run(
    start_agent=bloggy, 
    input={"blog_idea": "A blog about cats"}
)

```

Et voila! Now you get:

```python
{
    'funny_blog_title': '"Whisker Me This: The Purr-fect Guide to Cat-tastic Adventures"',
    'blog_headers': [
        "The Cat's Out of the Bag: Understanding Feline Behavior",
        'Paws and Reflect: The Secret Life of Cats',
        'Feline Fine: Health Tips for Your Kitty',
        "Cat-astrophic Cuteness: Why We Can't Resist Them",
        'Meow-sic to Your Ears: Communicating with Your Cat',
        'Claw-some Toys and Games: Keeping Your Cat Entertained',
        'The Tail End: Myths and Facts About Cats',
    ],
    'blog_idea': 'A blog about cats',
}

```

### Being pydantic

That's not enough for you, since you already got your data classes defined and don't want to redefine them again for some agents?

Also got some hard constraints, like the title needs to be in ALL CAPS? 🔥

Check this out:

```python
from pydantic import BaseModel, Field

class BlogSection(BaseModel):
    header: str
    content: str

class MyBlog(BaseModel):
    funny_blog_title: str = Field(description="The funny blog title in all caps")
    blog_sections: list[BlogSection]
```

Since flock is bein' pedantic about pydantic, you can just use your pydantic models like you would use type hints:

```python
bloggy = FlockAgent(
    name="bloggy", 
    input="blog_idea", 
    output="blog: MyBlog",
)
```

And BAM! Your finished data model filled up to the brim with data! 🎊


```python
{
  'blog': MyBlog(
      funny_blog_title='THE PURR-FECT LIFE: CATS AND THEIR QUIRKY ANTICS',
      blog_sections=[
          BlogSection(
              header='Introduction to the Feline World',
              content=(
                  'Cats have been our companions for thousands of years, yet they remain as mysterious and intriguin'
                  'g as ever. From their graceful movements to their independent nature, cats have a unique charm th'
                  "at captivates us. In this blog, we'll explore the fascinating world of cats and their quirky anti"
                  'cs that make them the purr-fect pets.'
              ),
          ),
          BlogSection(
              header='The Mysterious Ways of Cats',
              content=(
                  'Ever wonder why your cat suddenly sprints across the room at 3 AM or stares at a blank wall for h'
                  'ours? Cats are known for their mysterious behaviors that often leave us scratching our heads. The'
                  'se antics are not just random; they are deeply rooted in their instincts and natural behaviors. L'
                  "et's dive into some of the most common and puzzling cat behaviors."
              ),
          ),
          BlogSection(
              header="The Art of Napping: A Cat's Guide",
              content=(
                  "Cats are the ultimate nappers, spending up to 16 hours a day snoozing. But there's more to a catn"
                  'ap than meets the eye. Cats have perfected the art of napping, and each nap serves a purpose, whe'
                  "ther it's a quick power nap or a deep sleep. Learn how cats choose their napping spots and the sc"
                  'ience behind their sleep patterns.'
              ),
          ),
          BlogSection(
              header='The Great Cat Conspiracy: Do They Really Rule the World?',
              content=(
                  "It's a well-known fact among cat owners that cats secretly rule the world. With their ability to "
                  "manipulate humans into providing endless treats and belly rubs, it's no wonder they have us wrapp"
                  "ed around their little paws. Explore the humorous side of cat ownership and the 'conspiracy' theo"
                  'ries that suggest cats are the true overlords of our homes.'
              ),
          ),
          BlogSection(
              header='Conclusion: Why We Love Cats',
              content=(
                  'Despite their quirks and sometimes aloof nature, cats have a special place in our hearts. Their c'
                  "ompanionship, playful antics, and soothing purrs bring joy and comfort to our lives. Whether you'"
                  "re a lifelong cat lover or a new cat parent, there's no denying the unique bond we share with our"
                  " feline friends. So, here's to the purr-fect life with cats!"
              ),
          ),
      ],
  ),
  'blog_idea': 'A blog about cats',
}
```

### Building a chain gang

Our `bloggy` is great, but what if we want to turn those amazing headers into full blog posts? Time to bring in a friend! 🤝
Let's see how easy it is to make agents work together 🔗

```python
from flock.core import Flock, FlockAgent

flock = Flock(model="openai/gpt-4o")

# First agent: Our trusty bloggy generates titles and headers! 📝
bloggy = FlockAgent(
    name="bloggy",
    input="blog_idea: str|The topic to blog about",
    output=(
        "funny_blog_title: str|A catchy title for the blog, "
        "blog_headers: list[str]|List of section headers for the blog"
    )
)

# Second agent: The content wizard that brings headers to life! ✨
content_writer = FlockAgent(
    name="content_writer",
    input=(
        "funny_blog_title: str|The blog title to work with, "
        "blog_headers: list[str]|The headers to expand into content"
    ),
    output="blog_sections: list[BlogSection]|The fully written blog sections"
)

# Make them besties! 🤝
bloggy.hand_off = content_writer

# Add your dynamic duo to the flock
flock.add_agent(bloggy)
flock.add_agent(content_writer)

# Let them create some magic! 🎨
result = flock.run(
    input={"blog_idea": "A blog about cats"},
    start_agent=bloggy
)
```

Super simple rules to remember:
1. Point the first agent to the next one using `hand_off`
2. Make sure their inputs and outputs match up

### Tools of the trade

Of couse no agent framework is complete without using tools.
Flock enables agents to use any python function you pass as tool or to use one of the plenty default tools

```python
bloggy = FlockAgent(
    name="bloggy",
    input="blog_idea: str|The topic to blog about",
    output=(
        "funny_blog_title: str|A catchy title for the blog, "
        "blog_headers: list[str]|List of section headers for the blog"
        "analysis_results: dict[str,Any] | Result of calculated analysis if necessary"
    )
    tools=[basic_tools.web_search_duckduckgo, basic_tools.code_eval],
)

result = flock.run(
    input={"blog_idea": "A blog about cats, with an analysis how old the oldest cat became in days"},
    start_agent=bloggy
)
```

These tools are available out of the box (needs `flock-core[tools]`):

- web_search_tavily
- web_search_duckduckgo
- get_web_content_as_markdown
- get_anything_as_markdown (uses docling and needs `flock-core[all-tools]`)
- evaluate_math
- code_eval
- get_current_time
- count_words
- extract_urls
- extract_numbers
- json_parse_safe
- save_to_file
- read_from_file


That's all there is to it! `bloggy` comes up with amazing headers, and `content_writer` turns them into full blog sections. No more writer's block! 🎉

And this is just the beginning - you can chain as many agents as you want. Maybe add a proofreader? Or add memory? Or an SEO optimizer? But let's not get ahead of ourselves! 😉

So far we've barely scratched the surface of what flock has to offer, and we're currently hard at work building up the documentation for all the other super cool features Flock has up its sleeve! Stay tuned! 🚀

## Temporal Workflow Integration

Flock supports execution on Temporal, ensuring robust, fault-tolerant workflows:

- **Durability:** Persistent state management even in the case of failures.
- **Retries & Error Handling:** Automatic recovery via Temporal's built-in mechanisms.
- **Scalability:** Seamless orchestration of distributed agent workflows.

Documentation in progress!

## Architecture

<img src="docs/assets/images/components_chart.png" width="800"><br>

<img src="docs/assets/images/flow_chart.png" width="800"><br>


## Requirements

- Python 3.10+
- (Optional) Temporal server running locally for production-grade workflow features
- API keys for integrated services


recommended services
```bash
export OPENAI_API_KEY=sk-proj-
export TAVILY_API_KEY=tvly-
```

or in `.env`

For LLM interaction LiteLLM is getting used. Please refer to its documentation on how to easily use other models and/or provider.

https://docs.litellm.ai/docs/providers

## Installation

```bash
pip install flock-core
```

if you want to use the integrated tools

```bash
pip install flock-core[tools]
```

and for the docling tools

```bash
pip install flock-core[all-tools]
```

## Development


1. **Clone the Repository:**

   ```bash
   git clone https://github.com/whiteducksoftware/flock
   cd flock
   ```

2. **Create a Virtual Environment and sync all packages:**

   ```bash
   uv sync --all-groups --all-extras
   ```

3. **Install local version of flock:**

   ```bash
   uv build && uv pip install -e .
   ```

4. **Install Jaeger for telemetry**
    ```

    docker run -d --name jaeger \
      -e COLLECTOR_ZIPKIN_HTTP_PORT=9411 \
      -p 5775:5775/udp \
      -p 6831:6831/udp \
      -p 6832:6832/udp \
      -p 5778:5778 \
      -p 16686:16686 \
      -p 14268:14268 \
      -p 14250:14250 \
      -p 9411:9411 \
      jaegertracing/all-in-one:1.41


    ```

5. **Create your .env**

    Use `.env_template` as a template for you custom config variables


## Contributing

Contributions are welcome! Please submit Pull Requests and open issues on GitHub.

## License

This project is licensed under the terms of the LICENSE file included in the repository.

## Acknowledgments

- Built with [DSPy](https://github.com/stanfordnlp/dspy)
- Uses [Temporal](https://temporal.io/) for workflow management
- Integrates with [Tavily](https://tavily.com/) for web search capabilities

## Evolution & Future Direction

Flock was created to overcome the limitations of traditional agent frameworks. Key design goals include:

### Declarative Over Prompt Engineering

- **Simplify Agent Definitions:**  
  Focus on clear input/output contracts rather than long, complex prompts.
- **Model Agnostic:**  
  Change LLM backends without altering agent logic.
- **Improved Testability:**  
  Clear, structured interfaces facilitate unit testing and validation.

### Robust, Production-Grade Orchestration

- **Fault Tolerance:**  
  Leveraging Temporal for automatic retries, durable state, and robust error handling.
- **Scalability:**  
  Support for concurrent, batch, and distributed workflows.
- **Observability:**  
  Built-in logging and monitoring for real-time insights into workflow execution.

### Future Enhancements

- Expanded type system for richer agent interactions
- Enhanced tool ecosystem and custom integrations
- Advanced monitoring, debugging, and performance metrics
- Extended testing frameworks and validation tools

Join us in building the next generation of reliable, production-ready AI agent systems!
Become part of the FLOCK!

