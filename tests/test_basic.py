import pytest
from flock.agents.declarative_agent import DeclarativeAgent
from flock.core.flock import Flock


@pytest.mark.asyncio
async def test_create_and_run_agent():
    agent_runner = Flock(local_debug=True)

    agent = DeclarativeAgent(
        name="my_agent",
        input="long_text",
        output="title; headings: list[str]; entities_and_metadata: list[dict[str, str]]; type:Literal['news', 'blog', 'opinion piece', 'tweet']",
    )
    agent_runner.add_agent(agent)

    result = await agent_runner.run_async(
            start_agent=agent,
            input="""
The question has loomed over Democrats and their allies since Donald Trump was elected to a second term: Do party leaders and liberal, pro-democracy activists have the juice to launch a passionate, organized opposition to Trump and the Republican congressional trifecta?
The early takes, in the days and weeks after the election, were gloomy, bordering on defeatist. But less than a month now before Trump’s second inauguration, a picture is emerging of Resistance 2.0. It’s out with the “pink pussy hats” and often performative pop culture gesturing and in with strategic confrontation, from the halls of Congress to the courts and, when called for, the streets.
That, at least, is the plan.
“We don’t have rose-colored glasses. This is going to be a hard fight. They are more organized than they were last time. The landscape has moved further to the right in many ways in terms of the governmental balance of power,” said Skye Perryman, the leader of Democracy Forward, a left-leaning legal organization. “But there are real opportunities with both where the American people are on issues as well as with where the judicial landscape is.”
Organizers and activists repeated varying versions of this argument in dozens of interviews with CNN over the last few weeks: Yes, Trump and his movement are better poised to act than they were when he first entered the White House in 2017. But so are we. Democracy Forward, Perryman said, has been studying documents like Project 2025 and mapping out where legal battlegrounds and working with hundreds of lawyers from nearly 300 organizations to coordinate a proactive response to what she called a fundamentally unchanged far-right playbook.
Several groups, including those focused on immediate pressure points, like Trump’s mass deportation plans, said they expect supports to turn out in full force when inevitable crises emerge. There is also a growing sense that the GOP’s narrow congressional majorities are at risk of splintering under pressure from a well-organized opposition. The Republican bust-up over funding the government proves, advocates said — in conversations both before and after the fight exploded — that Trump’s agenda is ripe for spoiling.
“There will be policies that will cause clear riffs and divisions in their own base, in their own voter coalition,” said Maurice Mitchell, national director of the Working Families Party.
Those cracks are already showing up on Capitol Hill as some conservative Republican lawmakers butt heads with Trump and influential allies, like billionaire Elon Musk, over the outline of a spending bill to keep the government running.
‘There’s either going to be a movement or there isn’t’ """,
        )
    
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_create_and_run_agent_simple():
    agent_runner = Flock()

    agent = DeclarativeAgent(
        name="my_agent",
        input="blog_idea",
        output="funny_blog_title",
    )
    agent_runner._add_agent(agent)

    result = await agent_runner.run_async(
            start_agent=agent,
            input="cats",
        )
    
    assert isinstance(result, dict)
