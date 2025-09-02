import asyncio
import pytest

from flock.core.eval.program_predict import PredictProgram


@pytest.mark.p0
def test_predict_program_echoes_inputs_sync():
    prog = PredictProgram()
    out = asyncio.run(prog.run(inputs={"a": 1}))
    assert out == {"a": 1}


@pytest.mark.p0
def test_predict_program_stream_yields_final():
    prog = PredictProgram()

    async def _collect():
        chunks = []
        async for item in prog.run_stream(inputs={"x": "y"}):
            chunks.append(item)
        return chunks

    chunks = asyncio.run(_collect())
    assert len(chunks) == 1
    assert chunks[0]["event"] == "final"
    assert chunks[0]["result"] == {"x": "y"}

