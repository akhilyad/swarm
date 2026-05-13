"""Per-agent async event loop.

Each agent runs its own AgentLoop that:
1. Listens for incoming goals/messages on the message bus
2. Decomposes complex goals into sub-goals (for MANAGER/CEO)
3. Delegates sub-goals to children (for MANAGER/CEO)
4. Executes simple goals directly by calling the LLM (for WORKER)
5. Supports tool calling via LiteLLM native function-calling (no regex)
6. Synthesizes results and reports back up the hierarchy
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..communication.bus import MessageBus, Subscription
from ..communication.message import create_goal_message, create_reply, create_result_message
from ..core.node import NodeHandle
from ..core.types import Goal, GoalStatus, Message, MessageType, Role

logger = logging.getLogger(__name__)


class ClarificationNeeded(Exception):
    """Raised by a worker when it cannot complete a goal and needs the manager to clarify."""


class AgentLoop:
    """Async event loop for a single agent node."""

    def __init__(
        self,
        handle: NodeHandle,
        bus: MessageBus,
        llm_func: Any | None = None,
        tool_registry: Any | None = None,
        max_tool_iterations: int = 10,
    ) -> None:
        self.handle = handle
        self.bus = bus
        self.llm_func = llm_func  # Async callable: (prompt, context) -> str
        self.tool_registry = tool_registry
        self.max_tool_iterations = max_tool_iterations
        self._running = False
        self._subscriptions: list[Subscription] = []
        self._active_goals: dict[str, Goal] = {}

    async def start(self) -> None:
        """Start listening for messages on the agent's inbox topic."""
        self._running = True
        sub = self.bus.subscribe(self.handle.node_id, self._on_message)
        self._subscriptions.append(sub)

        # Restore any goals that were in-flight before a crash
        for goal in self.bus.get_active_goals():
            if goal.assignee_id == self.handle.node_id:
                self._active_goals[goal.goal_id] = goal
                logger.info(
                    "Restored persisted goal %s for agent %s",
                    goal.goal_id, self.handle.name,
                )

        logger.info("Agent %s started, listening on '%s'", self.handle.name, self.handle.node_id)

    async def stop(self) -> None:
        """Stop the agent loop and clean up subscriptions."""
        self._running = False
        for sub in self._subscriptions:
            sub.unsubscribe()
        self._subscriptions.clear()
        logger.info("Agent %s stopped", self.handle.name)

    async def _on_message(self, message: Message) -> None:
        """Handle an incoming message."""
        logger.debug("Agent %s received: %s", self.handle.name, message)

        if message.type == MessageType.GOAL:
            asyncio.create_task(self._handle_goal(message))
        elif message.type == MessageType.CANCEL:
            asyncio.create_task(self._handle_cancel(message))
        elif message.type == MessageType.QUERY:
            asyncio.create_task(self._handle_query(message))
        elif message.type == MessageType.STATUS:
            asyncio.create_task(self._handle_status(message))
        elif message.type == MessageType.CLARIFY:
            asyncio.create_task(self._handle_clarify(message))

    async def _handle_goal(self, message: Message) -> None:
        """Process an incoming goal delegation."""
        goal = Goal(
            description=message.content,
            assignee_id=self.handle.node_id,
            parent_goal_id=message.goal_id,
        )
        self.handle.assign_goal(goal)
        self._active_goals[goal.goal_id] = goal
        result: str = ""

        try:
            has_children = len(self.handle.node.child_ids) > 0
            if has_children and self.handle.role in (Role.CEO, Role.MANAGER):
                result = await self._decompose_and_delegate(goal)
            else:
                result = await self._execute_goal(goal)

            goal.status = GoalStatus.COMPLETED
            goal.result = result

            reply = create_result_message(
                sender=self.handle.node_id,
                recipient=message.sender,
                result=result,
                goal_id=message.goal_id,
                correlation_id=message.correlation_id,
            )
            await self.bus.publish(reply)

        except ClarificationNeeded as clarify:
            # Worker cannot complete the goal — ask the manager for help
            logger.info(
                "Agent %s needs clarification on goal %s: %s",
                self.handle.name, goal.goal_id, clarify,
            )

            clarify_msg = self._make_clarify_message(
                message=message,
                question=str(clarify),
            )
            await self.bus.publish(clarify_msg)

            # Pause and wait for the manager to respond
            response = await self._wait_for_clarify_response(
                goal_id=goal.goal_id,
                timeout=60.0,
            )

            if response is not None:
                # Retry with clarified instructions
                goal.description = f"{message.content}\n\nClarification from manager: {response.content}"
                try:
                    result = await self._execute_goal(goal)
                    goal.status = GoalStatus.COMPLETED
                    goal.result = result

                    reply = create_result_message(
                        sender=self.handle.node_id,
                        recipient=message.sender,
                        result=result,
                        goal_id=message.goal_id,
                        correlation_id=message.correlation_id,
                    )
                    await self.bus.publish(reply)
                except ClarificationNeeded:
                    # Still stuck after clarification — give up
                    goal.status = GoalStatus.FAILED
                    goal.error = "Unable to complete even after clarification"
                    reply = Message(
                        type=MessageType.ERROR,
                        sender=self.handle.node_id,
                        recipient=message.sender,
                        content="Worker unable to complete goal after clarification",
                        goal_id=message.goal_id,
                        correlation_id=message.correlation_id,
                    )
                    await self.bus.publish(reply)
            else:
                # No response from manager — fail
                goal.status = GoalStatus.FAILED
                goal.error = "Manager did not respond to clarification request"
                reply = Message(
                    type=MessageType.ERROR,
                    sender=self.handle.node_id,
                    recipient=message.sender,
                    content="Worker timed out waiting for clarification",
                    goal_id=message.goal_id,
                    correlation_id=message.correlation_id,
                )
                await self.bus.publish(reply)

        except Exception as e:
            goal.status = GoalStatus.FAILED
            goal.error = str(e)
            logger.exception("Goal %s failed for agent %s", goal.goal_id, self.handle.name)

            reply = Message(
                type=MessageType.ERROR,
                sender=self.handle.node_id,
                recipient=message.sender,
                content=str(e),
                goal_id=message.goal_id,
                correlation_id=message.correlation_id,
            )
            await self.bus.publish(reply)
        finally:
            self.handle.complete_goal(result)
            self._active_goals.pop(goal.goal_id, None)

    def _make_clarify_message(self, message: Message, question: str) -> Message:
        """Create a CLARIFY message addressed to the original sender."""
        return Message(
            type=MessageType.CLARIFY,
            sender=self.handle.node_id,
            recipient=message.sender,
            content=question,
            goal_id=message.goal_id,
            correlation_id=message.correlation_id,
            in_reply_to=message.message_id,
        )

    async def _wait_for_clarify_response(self, goal_id: str, timeout: float) -> Message | None:
        """Subscribe and wait for a CLARIFY reply targeting the given goal."""
        future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()

        async def _clarify_listener(msg: Message) -> None:
            if not future.done():
                future.set_result(msg)

        sub = self.bus.subscribe(self.handle.node_id, _clarify_listener)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            sub.unsubscribe()

    async def _handle_clarify(self, message: Message) -> None:
        """A manager receives a CLARIFY from a worker — ask LLM and respond."""
        logger.info(
            "Manager %s handling CLARIFY from %s: %s",
            self.handle.name, message.sender, message.content,
        )

        if not self.llm_func:
            # No LLM — just acknowledge (worker will retry with original goal)
            reply = Message(
                type=MessageType.CLARIFY,
                sender=self.handle.node_id,
                recipient=message.sender,
                content="Re-try the original goal with your best judgment.",
                goal_id=message.goal_id,
                correlation_id=message.correlation_id,
                in_reply_to=message.message_id,
            )
            await self.bus.publish(reply)
            return

        # Ask the LLM to provide clearer instructions
        clarification = await self.llm_func(
            f"A worker ({message.sender}) needs clarification on a goal.\n\n"
            f"The worker says: {message.content}\n\n"
            f"Provide clearer, more specific instructions so the worker can "
            f"complete the goal. Be concrete and actionable.",
            {"role": self.handle.role.value},
        )

        reply = Message(
            type=MessageType.CLARIFY,
            sender=self.handle.node_id,
            recipient=message.sender,
            content=clarification,
            goal_id=message.goal_id,
            correlation_id=message.correlation_id,
            in_reply_to=message.message_id,
        )
        await self.bus.publish(reply)

    async def _execute_goal(self, goal: Goal) -> str:
        """Execute a goal directly using LiteLLM native tool calling.

        WORKER agents execute goals by calling the LLM. If tools are
        registered, the LLM can invoke them through the structured
        function-calling API (no brittle regex parsing). The loop
        continues until the LLM produces a final text response or the
        iteration limit is reached.

        Raises ``ClarificationNeeded`` if the goal cannot be completed
        and the manager must provide clearer instructions.
        """
        if not self.llm_func:
            return f"[{self.handle.name}] executed: {goal.description}"

        prompt = self._build_tool_prompt(goal.description)
        conversation = [prompt]
        openai_tools = (
            self.tool_registry.get_openai_tools()
            if self.tool_registry and self.tool_registry.tool_count > 0
            else None
        )

        for iteration in range(self.max_tool_iterations):
            response = await self.llm_func(
                conversation[-1] if len(conversation) == 1
                else f"{conversation[-1]}\n\n[CONTEXT]\n{goal.description}",
                {"role": self.handle.role.value, "iteration": iteration},
                tools=openai_tools,
            )

            # No tool call -> final answer
            if not response.tool_calls:
                return response.content or ""

            # Execute each tool call the LLM made
            for tc in response.tool_calls:
                tool = self.tool_registry.get_tool(tc.name) if self.tool_registry else None
                if tool is None:
                    conversation.append(
                        f"[Tool '{tc.name}' is not available. "
                        f"Available tools: {self.tool_registry.list_capabilities() if self.tool_registry else 'none'}]"
                    )
                    continue

                result = await tool.execute(**tc.arguments)
                if result.success:
                    conversation.append(
                        f"[Tool '{tc.name}' returned]:\n{result.output}"
                    )
                else:
                    conversation.append(
                        f"[Tool '{tc.name}' error]:\n{result.error}"
                    )

        # Worker exhausted all tool iterations without producing a final answer
        raise ClarificationNeeded(
            f"I am {self.handle.name} and I could not complete the goal after "
            f"{self.max_tool_iterations} tool iterations. "
            f"The goal may be too complex or ambiguous. "
            f"Please provide more specific, step-by-step instructions."
        )

    def _build_tool_prompt(self, goal: str) -> str:
        """Build the initial LLM prompt."""
        lines = [
            f"You are {self.handle.name}, a {self.handle.role.value} agent.",
            "",
            f"Goal: {goal}",
            "",
        ]

        if self.tool_registry and self.tool_registry.tool_count > 0:
            lines.append("You have access to tools — use them when needed to accomplish the goal.")
            lines.append("")
            lines.append(self.tool_registry.list_capabilities())
        else:
            lines.append("Respond with the result of your work.")
            lines.append("")

        return "\n".join(lines)

    async def _decompose_and_delegate(self, goal: Goal) -> str:
        """Decompose a goal into sub-goals and delegate to children.

        MANAGER/CEO agents decompose complex goals into smaller pieces,
        assign each piece to a child agent, collect results, and synthesize.
        """
        children = [c for c in self.handle.node.child_ids]

        if not children:
            return await self._execute_goal(goal)

        # Decompose: use LLM to break down the goal
        if self.llm_func:
            decomposition = await self.llm_func(
                f"Decompose the following goal into sub-tasks for your team members. "
                f"Your team members are: {', '.join(children)}.\n\nGoal: {goal.description}",
                {"role": self.handle.role.value, "children": children},
            )
        else:
            decomposition = goal.description

        # Delegate: create sub-goals and assign to children
        sub_results: dict[str, str] = {}
        response_futures: dict[str, asyncio.Future] = {}

        async def collect_result(msg: Message) -> None:
            if msg.goal_id and msg.goal_id in response_futures:
                if not response_futures[msg.goal_id].done():
                    response_futures[msg.goal_id].set_result(msg.content)

        collector_sub = self.bus.subscribe(self.handle.node_id, collect_result)

        try:
            for child_id in children:
                sub_goal = Goal(
                    description=f"{decomposition}\n[Assigned to: {child_id}]",
                    assignee_id=child_id,
                    parent_goal_id=goal.goal_id,
                )
                goal.sub_goal_ids.append(sub_goal.goal_id)

                future = asyncio.get_event_loop().create_future()
                response_futures[sub_goal.goal_id] = future

                msg = create_goal_message(
                    sender=self.handle.node_id,
                    recipient=child_id,
                    goal_description=sub_goal.description,
                    goal_id=sub_goal.goal_id,
                    correlation_id=goal.goal_id,
                )
                await self.bus.publish(msg)

            # Collect results with timeout
            for child_id, sub_goal_id in zip(children, list(response_futures.keys())):
                try:
                    result = await asyncio.wait_for(
                        response_futures[sub_goal_id], timeout=30.0
                    )
                    sub_results[child_id] = result
                except asyncio.TimeoutError:
                    sub_results[child_id] = f"[{child_id}] timed out"
        finally:
            collector_sub.unsubscribe()

        # Synthesize: combine results
        if self.llm_func and sub_results:
            summary_input = "\n".join(
                f"{agent}: {result}" for agent, result in sub_results.items()
            )
            synthesis = await self.llm_func(
                f"Synthesize these results into a final response:\n\n{summary_input}",
                {"role": self.handle.role.value},
            )
            return synthesis

        return "\n".join(f"{agent}: {result}" for agent, result in sub_results.items())

    async def _handle_cancel(self, message: Message) -> None:
        """Cancel an active goal."""
        if message.goal_id and message.goal_id in self._active_goals:
            goal = self._active_goals[message.goal_id]
            goal.status = GoalStatus.CANCELLED
            logger.info("Goal %s cancelled for agent %s", message.goal_id, self.handle.name)

    async def _handle_query(self, message: Message) -> None:
        """Respond to a query message."""
        reply = create_reply(message, self.handle.node_id, f"[{self.handle.name}] status: active")
        await self.bus.publish(reply)

    async def _handle_status(self, message: Message) -> None:
        """Report agent status."""
        status_info = (
            f"Agent: {self.handle.name}\n"
            f"Role: {self.handle.role.value}\n"
            f"Active: {self.handle.is_active}\n"
            f"Busy: {self.handle.is_busy}\n"
            f"Active Goals: {len(self._active_goals)}"
        )
        reply = create_reply(message, self.handle.node_id, status_info)
        await self.bus.publish(reply)
