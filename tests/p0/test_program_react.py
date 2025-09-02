import asyncio
import pytest

from flock.core.eval.program_react import ReActProgram


def add(a: int, b: int) -> int:
    """Return a + b."""
    return a + b


@pytest.mark.p0
def test_react_program_echoes_inputs_without_model():
    prog = ReActProgram(tools={"add": add})
    out = asyncio.run(prog.run(inputs={"x": 1}))
    assert out == {"x": 1}


@pytest.mark.p0
def test_react_program_stream_yields_final_without_model():
    prog = ReActProgram(tools={"add": add})

    async def _collect():
        chunks = []
        async for item in prog.run_stream(inputs={"q": "z"}):
            chunks.append(item)
        return chunks

    chunks = asyncio.run(_collect())
    assert chunks and chunks[-1]["event"] == "final"
    assert chunks[-1]["result"] == {"q": "z"}

