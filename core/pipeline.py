"""
Pipeline Orchestrator — Multi-Agent coordination.

Orchestrates a sequence of agents, where each agent's structured output
becomes the next agent's input. Supports:

  - Pipeline: sequential agent execution (default)
  - Retry with feedback: Judge Agent rejects → Write Agent revises
  - Observability: every stage is recorded
  - Partial failure: one agent failing doesn't kill the whole pipeline
"""

import logging
import time
from typing import Any, Callable

from .agent import BaseAgent, AgentContext
from .observer import Observer
from .structured_output import SchemaValidationError

logger = logging.getLogger(__name__)


class PipelineStage:
    """A single stage in the pipeline."""

    def __init__(
        self,
        name: str,
        agent: BaseAgent,
        input_transform: Callable | None = None,
        output_transform: Callable | None = None,
        max_retries: int = 1,
        critical: bool = True,  # If True, pipeline aborts on failure
    ):
        self.name = name
        self.agent = agent
        self.input_transform = input_transform
        self.output_transform = output_transform
        self.max_retries = max_retries
        self.critical = critical


class PipelineResult:
    """Result of a full pipeline run."""

    def __init__(self):
        self.stages: list[dict] = []
        self.final_output: Any = None
        self.error: str | None = None
        self.duration: float = 0.0
        self.success: bool = False


class PipelineOrchestrator:
    """
    Orchestrates a sequence of agents.

    Usage:
        orchestrator = PipelineOrchestrator(observer)
        orchestrator.add_stage("capture", capture_agent)
        orchestrator.add_stage("analyze", analyze_agent)
        result = orchestrator.run({"date": "2026-06-09"})
    """

    def __init__(self, observer: Observer | None = None):
        self.stages: list[PipelineStage] = []
        self.observer = observer or Observer()

    def add_stage(
        self,
        name: str,
        agent: BaseAgent,
        input_transform: Callable | None = None,
        output_transform: Callable | None = None,
        max_retries: int = 1,
        critical: bool = True,
    ):
        """Add a stage to the pipeline. Critical stages abort the pipeline on failure."""
        self.stages.append(PipelineStage(
            name=name,
            agent=agent,
            input_transform=input_transform,
            output_transform=output_transform,
            max_retries=max_retries,
            critical=critical,
        ))

    def run(self, initial_input: Any, pipeline_state: Any | None = None) -> PipelineResult:
        """
        Execute the pipeline sequentially with optional resume support.

        If pipeline_state is provided, completed stages are skipped and
        their cached outputs are loaded. Only uncompleted/failed stages run.

        Each stage's output is passed as input to the next stage,
        with optional transforms applied between stages.
        """
        result = PipelineResult()
        start_time = time.perf_counter()
        current_input = initial_input

        self.observer.log(f"Pipeline starting with {len(self.stages)} stages")

        for stage in self.stages:
            stage_start = time.perf_counter()
            stage_record = {
                "name": stage.name,
                "duration": 0,
                "error": None,
                "retries": 0,
            }

            # Resume: skip if this stage already completed
            if pipeline_state and pipeline_state.is_completed(stage.name):
                cached = pipeline_state.get_output(stage.name)
                if cached is not None:
                    current_input = cached
                    stage_record["duration"] = 0
                    stage_record["note"] = "resumed from cache"
                    self.observer.log(f"Stage '{stage.name}' → skipped (cached)")
                    result.stages.append(stage_record)
                    continue
                # Cached output missing — re-run
                pipeline_state.fail_stage(stage.name, "cached output missing")
                self.observer.log(f"Stage '{stage.name}' → cache miss, re-running")

            try:
                # Apply input transform if specified
                if stage.input_transform:
                    current_input = stage.input_transform(current_input)

                # Run the agent
                agent_output = stage.agent.run(current_input)

                # Apply output transform if specified
                if stage.output_transform:
                    agent_output = stage.output_transform(agent_output)

                current_input = agent_output
                stage_record["duration"] = round(time.perf_counter() - stage_start, 3)
                self.observer.log(f"Stage '{stage.name}' completed in {stage_record['duration']}s")
                result.stages.append(stage_record)
                if pipeline_state:
                    # For publish stage, only mark complete if any platform succeeded
                    if stage.name == "publish":
                        pub_results = agent_output.get("results", []) if isinstance(agent_output, dict) else []
                        any_ok = any(r.get("success") for r in pub_results)
                        if any_ok:
                            pipeline_state.complete_stage(stage.name, agent_output)
                            for r in pub_results:
                                pipeline_state.record_publish_result(
                                    r.get("platform", "?"),
                                    r.get("success", False),
                                    r.get("url", ""),
                                    r.get("error", ""),
                                )
                    else:
                        pipeline_state.complete_stage(stage.name, agent_output)

            except SchemaValidationError as e:
                stage_record["error"] = f"Schema validation failed: {e}"
                stage_record["duration"] = round(time.perf_counter() - stage_start, 3)
                self.observer.log(f"Stage '{stage.name}' schema validation failed")
                result.stages.append(stage_record)
                if pipeline_state:
                    pipeline_state.fail_stage(stage.name, str(e))
                if stage.critical:
                    self.observer.log(f"Stage '{stage.name}' is critical — aborting pipeline")
                    result.success = False
                    result.duration = round(time.perf_counter() - start_time, 3)
                    return result
            except Exception as e:
                stage_record["error"] = str(e)
                stage_record["duration"] = round(time.perf_counter() - stage_start, 3)
                self.observer.log(f"Stage '{stage.name}' failed: {e}")
                result.stages.append(stage_record)
                if pipeline_state:
                    pipeline_state.fail_stage(stage.name, str(e))
                if stage.critical:
                    self.observer.log(f"Stage '{stage.name}' is critical — aborting pipeline")
                    result.success = False
                    result.duration = round(time.perf_counter() - start_time, 3)
                    return result

        result.duration = round(time.perf_counter() - start_time, 3)
        result.final_output = current_input
        result.success = all(s["error"] is None for s in result.stages)

        self.observer.record_pipeline_run(
            pipeline_name="daily_pipeline",
            stages=result.stages,
            duration=result.duration,
            error=result.error,
        )

        return result


class JudgeLoopPipeline:
    """
    Extended pipeline with a Judge loop.

    After Write Agent produces an article, Judge Agent evaluates it.
    If quality is below threshold, Write Agent revises with feedback.
    This continues until Judge passes or max iterations reached.
    """

    def __init__(
        self,
        write_agent: BaseAgent,
        judge_agent: BaseAgent,
        observer: Observer | None = None,
        max_iterations: int = 3,
        pass_threshold: int = 70,
        experience_store: Any = None,
        renderer: Any = None,
        polisher: Any = None,
    ):
        self.write_agent = write_agent
        self.judge_agent = judge_agent
        self.observer = observer or Observer()
        self.max_iterations = max_iterations
        self.pass_threshold = pass_threshold
        self.experience_store = experience_store
        self.renderer = renderer
        self.polisher = polisher

    def run(self, input_data: Any) -> tuple[dict, list[dict]]:
        """
        Run write-evaluate loop.

        Returns:
            (final_article, iteration_history)
        """
        history = []

        for iteration in range(self.max_iterations):
            self.observer.log(f"Judge loop iteration {iteration + 1}/{self.max_iterations}")

            # Inject experience context (past high-scoring patterns)
            experience_context = ""
            if self.experience_store and iteration == 0:
                try:
                    experience_context = self.experience_store.get_context_for_writer()
                    if experience_context:
                        self.observer.log(f"Experience store: injected {len(experience_context)} chars of past patterns")
                except Exception as e:
                    self.observer.log(f"Experience store unavailable: {e}")
                    experience_context = ""

            # Build enriched input
            enriched_input = {
                **input_data,
                "iteration": iteration + 1,
                "experience_context": experience_context,
            }
            if iteration > 0:
                enriched_input["previous_feedback"] = history[-1]

            # Write
            article = self.write_agent.run(enriched_input)

            # Render via template (converts JSON → Markdown for Judge to evaluate)
            if self.renderer:
                try:
                    article["content"] = self.renderer.render(article, "devto")
                    article["wechat_html"] = self.renderer.render(article, "wechat_mp")
                except Exception as e:
                    self.observer.log(f"Template render failed: {e}")

            # Polish — improve writing quality (voice, flow, hooks, title)
            if self.polisher and iteration == 0:
                try:
                    polished = self.polisher.run({
                        "title": article.get("title", ""),
                        "content": article.get("content", ""),
                        "tags": article.get("tags", []),
                    })
                    article["title"] = polished.get("title", article.get("title", ""))
                    article["content"] = polished.get("content", article.get("content", ""))
                    article["polish_changes"] = polished.get("changes_made", [])
                    self.observer.log(f"Polisher: {len(polished.get('changes_made', []))} changes")
                except Exception as e:
                    self.observer.log(f"Polisher skipped: {e}")

            # Judge
            judge_input = {
                "article": article,
                "iteration": iteration + 1,
            }
            verdict = self.judge_agent.run(judge_input)

            history.append({
                "iteration": iteration + 1,
                "article_summary": str(article.get("title", ""))[:100] if article else "",
                "score": verdict.get("score", 0),
                "verdict": verdict.get("verdict", "fail"),
                "feedback": verdict.get("feedback", []),
            })

            # Check if passed
            # Record experience
            if self.experience_store:
                try:
                    self.experience_store.record(
                        date=input_data.get("date", ""),
                        tags=input_data.get("tags", []),
                        score=verdict.get("score", 0),
                        dimensions=verdict.get("dimensions", {}),
                        feedback=verdict.get("feedback", []),
                        verdict=verdict.get("verdict", "unknown"),
                        article_title=article.get("title", ""),
                        article_snippet=article.get("content", ""),
                        iteration=iteration + 1,
                    )
                except Exception:
                    pass

            if verdict.get("verdict") == "pass" and verdict.get("score", 0) >= self.pass_threshold:
                self.observer.log(f"✅ Article passed judge with score {verdict.get('score')}")
                return article, history

            if iteration < self.max_iterations - 1:
                self.observer.log(f"Article scored {verdict.get('score')}/{self.pass_threshold}, revising...")

        # Raise if never passed
        last_score = history[-1].get("score", 0) if history else 0
        raise ValueError(
            f"Article failed quality gate: best score {last_score}/{self.pass_threshold} "
            f"after {self.max_iterations} iterations. Feedback: {history[-1].get('feedback', []) if history else 'N/A'}"
        )
