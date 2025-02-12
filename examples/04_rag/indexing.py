
import asyncio
from dataclasses import dataclass
from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.tools import basic_tools


@dataclass
class File:
    file_path: str
    file_content_as_markdown:str

FileList = list[File]

async def main():
    flock = Flock(local_debug=True)


    indexer = FlockAgent(name="indexer_agent",
                    description="Indexes the files in a folder, and converts them to markdown",
                      input="folder_path",
                      output="list_of_files: FileList",
                      tools=[basic_tools])
    
    flock.add_agent(indexer)
    await flock.run_async(indexer, input={"folder_path": "E:\\_ai\\data\\KITE\\knowledge-base-content\\ai-papers\\small"})


if __name__ == "__main__":
    # Run the main coroutine using asyncio
    asyncio.run(main())


