import asyncio
import pytest

from flock.core.eval.program_llmcompiler import LLMCompilerProgram


def tool_upper(text: str) -> str:
    """Uppercase a string."""
    return text.upper()


@pytest.mark.p0
def test_llmcompiler_program_echoes_inputs_without_model():
    prog = LLMCompilerProgram(tools={"tool_upper": tool_upper})
    out = asyncio.run(prog.run(inputs={"msg": "hello"}))
    assert out == {"msg": "hello"}


@pytest.mark.p0
def test_llmcompiler_program_stream_yields_final_without_model():
    prog = LLMCompilerProgram(tools={"tool_upper": tool_upper})

    async def _collect():
        chunks = []
        async for item in prog.run_stream(inputs={"msg": "hi"}):
            chunks.append(item)
        return chunks

    chunks = asyncio.run(_collect())
    assert chunks and chunks[-1]["event"] == "final"
    assert chunks[-1]["result"] == {"msg": "hi"}

