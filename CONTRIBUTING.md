<!-- TOC --><a name="contributing-to-flock"></a>
# Contributing to Flock

First off, thanks for taking the time to contribute!
Flock is still in early development but we value outside input. ❤️

We follow the [Contributor Covenant](https://www.contributor-covenant.org/) code of conduct.

## Table of Contents:
<!-- TOC start -->

- [Contributing to Flock](#contributing-to-flock)
   * [🗒️ Getting Started:](#-getting-started)
   * [❗ Reporting Issues:](#-reporting-issues)
   * [🚋 Pull Requests: ](#-pull-requests)
   * [💻 Coding Standards: ](#-coding-standards)
      + [General Standards:](#general-standards)
      + [A few best practices for writing good code:](#a-few-best-practices-for-writing-good-code)
         - [Embrace Declarative Programming Principles:](#embrace-declarative-programming-principles)
         - [Consistent Code Formatting:](#consistent-code-formatting)
         - [Meaningful Naming Conventions:](#meaningful-naming-conventions)
         - [Modular and Composable Code:](#modular-and-composable-code)
   * [📖 Documentation Guidelines: ](#-documentation-guidelines)
      + [A few best practices for writing good documentation:](#a-few-best-practices-for-writing-good-documentation)
   * [🔭 Testing and Reliability:](#-testing-and-reliability)
   * [Release Process:](#release-process)

<!-- TOC end -->

<!-- TOC --><a name="-getting-started"></a>
## 🗒️ Getting Started:
1. Fork the repo & create your feature branch (`git checkout -b feat/my-awesome-thing`).
2. Install dev dependencies: `uv pip install -r requirements.txt && uv pip install -r requirements-dev.txt.`
3. Run tests: `pytest -q` (they should pass before and after your change).
4. Make changes – keep them atomic and well-documented.
5. Lint & type-check: `ruff .` and `mypy src/.`
6. Commit following Conventional Commits (`feat:`, `fix:`, `docs:` etc.).
7. Open a PR against main. Include a description, screenshots, and linked issues.


<!-- TOC --><a name="-reporting-issues"></a>
## ❗ Reporting Issues:
- Before submitting a new issue, please check [existing issues](https://github.com/whiteducksoftware/flock/issues) if it has already been reported.
- To submit a new issue, please use the provided **Issue Templates** and provide a clear and descriptive title along with a detailed description of the problem or feature request, including steps to reproduce if it's a bug.

<!-- TOC --><a name="-pull-requests"></a>
## 🚋 Pull Requests: 
- Ensure your code is well-tested and adheres to the [Coding Standards](#code-standards) outlined below.
- Write clear commit messages that explain the changes made.
- Clearly outline and communicate breaking API-changes.
- Before submitting a pull request, make sure your branch is up to date with the base branch (`main`) of the [main repository](https://github.com/whiteducksoftware/flock).
- Open a pull request with a summary of your changes and any relevant issue numbers.

<!-- TOC --><a name="-coding-standards"></a>
## 💻 Coding Standards: 
- Flock follows a **declarative** approach and design philosophy. Make sure that your code follows this principle.
- Follow the coding conventions used within the existing codebase.
- Keep code modular and readable. Prefer clarity over brevity.
- Include comments where necessary and explain complex logic.

<!-- TOC --><a name="general-standards"></a>
### General Standards:
- Python `3.10.+`. Use type hints everywhere.
- Follow [`ruff`](https://docs.astral.sh/ruff/) default rules + [`black`](https://black.readthedocs.io/en/stable/index.html) formatting.
- Keep imports sorted (`ruff format`)
- Write **async-friendly** code. (non-blocking I/O)

<!-- TOC --><a name="a-few-best-practices-for-writing-good-code"></a>
### A few best practices for writing good code:

<!-- TOC --><a name="embrace-declarative-programming-principles"></a>
#### Embrace Declarative Programming Principles:
- **Favor Declarative Styles**:
   - Exposed API-Code should express the desired results rather than detailing the control flow of the program.
   - Use declarative constructs to define behavior instead of imperative constructs where applicable.
   - Aim for expressiveness and clarity in stating "what" should happen rather than "how" it should happen.
- **Use High-Level Abstractions**:
   - Leverage Flock's existing abstractions to minimize boilerplate code and simplify the implementation.
   - This makes the code easier to read and understand.
<!-- TOC --><a name="consistent-code-formatting"></a>
#### Consistent Code Formatting:
- **Adhere to Existing Code Style**: Consistency in formatting enhances readability and helps developers navigate the codebase.
<!-- TOC --><a name="meaningful-naming-conventions"></a>
#### Meaningful Naming Conventions:
- **Use Descriptive Names**:
  - Choose variable, function, and class names that clearly describe their purpose.
  - Be consistent. Stick to the naming conventions in Flock's existing code-base.
<!-- TOC --><a name="modular-and-composable-code"></a>
#### Modular and Composable Code:
- **Write Modular Code**: Break down complex logic into smaller, reusable components.
- **Avoid Side Effects**: Aim to minimize side effects where possible.


<!-- TOC --><a name="-documentation-guidelines"></a>
## 📖 Documentation Guidelines: 
- Documentation lives under [`docs/`](https://github.com/whiteducksoftware/flock/tree/master/docs), and is built with [MkDocs Material](https://github.com/squidfunk/mkdocs-material).
- Good documentation is crucial for the usability of Flock. When adding or updating code, please also update the relevant documentation.
- Use clear, concise language and include examples where applicable. (On that note: If you want to, you may also provide an example for the [example showcase](https://github.com/whiteducksoftware/flock-showcase)
- Maintain consistency in formatting and style throughout the documentation.
- Use American English
- Keep sentences short; favour lists & tables.
- Add code blocks with triple-backticks and language.

<!-- TOC --><a name="a-few-best-practices-for-writing-good-documentation"></a>
### A few best practices for writing good documentation:
1. Document the **Why**, not just the how:
    - Documentation should explain the rationale behind your decisions, rather than just describing the "how".
    - This helps other developers understand the context and reasoning for the implementation, making the code more maintainable and modifiable.
2. Keep it Up to Date:
   - Your documentation should evolve alongside the code. If you change the behavior of an existing component of Flock, please also take care to make sure the documentation reflects this fact.
3. Write for the Reader:
   - Consider the audience for your documentation.
   - It should be accessible and understandable for developers who are not intimately familiar with the code.
4. Document Intent and Design:
   - Referring to Point 1, Document your decisions of **why** you chose to implement a new component or code change the way you did, if it is not immediately obvious.
5. Code as Documentation:
   - Well-written code can serve as it's own documentation.
   - Code should be clear, expressive and self-explanatory where possible.
   - Using meaningful names for variables, functions, and classes can reduce the need for excessive comments.
6. Provide Examples:
   - Examples can help other developers understand your changes and are therefore encouraged.
7. Use Comments Wisely:
   - Avoid redundant comments that merely restate what the code does, which can clutter the codebase and detract from its readability.
8. Be Pragmatic:
   - There is no need for you to excessively comment every line of code you provide.
   - Add documentation where necessary and focus on keeping documentation on a high level.

<!-- TOC --><a name="-testing-and-reliability"></a>
## 🔭 Testing and Reliability:
Flock aims to provide an easy and reliable way to implement agentic applications. Therefore, well tested code is crucial.

Start here:
- Strategy: see `docs/testing_strategy.md` for priorities and coverage goals.
- How-to: see `docs/testing_guide.md` for setup, patterns, and examples.
- TODOs (internal): see `docs/internal/testing_todo.md`.

Run tests with uv (recommended):
- Quick suite (CI-equivalent): `uv run poe test`
- Full/nightly: `uv run poe test-all`
- Select markers: `uv run pytest -m 'p0 or integration'`

Guidelines:
- Ensure existing tests pass and add **new tests** for new or changed functionality.
- Prefer deterministic, isolated tests using fixtures in `tests/conftest.py` and helpers in `tests/_helpers`.
- Place tests under `tests/` by concern (see strategy structure).
- Use [`pytest`](https://docs.pytest.org/en/stable/) fixtures instead of duplicating setup code.

### Pydantic I/O and Hydrator
- Agents may define input/output contracts using Pydantic models as an alternative to string contracts. See `AGENT.md#pydantic-io-contracts-new` for examples and guidelines.
- To generate structured data with an LLM into a model instance, use the hydrator decorator. See `AGENT.md#hydrator-pydantic`.


<!-- TOC --><a name="release-process"></a>
## Release Process:
1. Maintainer bumps version in `pyproject.toml` following **SemVer**.
2. Changelog entry added in `docs/about/changelog.md`.
3. `uv pip install -e .[all] && pytest`
4. `git tag v.X.Y.Z && git push --tags`
5. GitHub Action publishes to PyPI.

Thank you for contributing to Flock, the declarative Agent-Framework. 🦆💓
