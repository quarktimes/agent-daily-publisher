"""
Daily Pipeline — Full daily publishing workflow.

This is the main entry point that orchestrates the entire multi-agent pipeline:
  Capture → Analyze → Write → [Judge ↻] → Adapt → Publish

Usage:
    python -m workflows.daily_pipeline                          # today, dry run
    python -m workflows.daily_pipeline --date 2026-06-09        # specific date
    python -m workflows.daily_pipeline --publish                 # live publish
    python -m workflows.daily_pipeline --no-judge                # skip quality check
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.observer import Observer
from core.pipeline import PipelineOrchestrator, JudgeLoopPipeline

from agents.capture_agent import CaptureAgent
from agents.analyze_agent import AnalyzeAgent
from agents.write_agent import WriteAgent
from agents.judge_agent import JudgeAgent
from agents.adapt_agent import AdaptAgent
from agents.interview_agent import InterviewAgent
from agents.polisher_agent import PolisherAgent
from agents.publish_agent import PublishAgent

from tools.article_formatter import save_article
from tools.privacy_filter import (
    sanitize_input,
    validate_article_safe,
    add_privacy_instruction_to_prompt,
)
from tools.template_renderer import TemplateRenderer
from tools.cover_image import generate_cover
from tools.publishers.devto import DevToPublisher
from tools.publishers.juejin import JuejinPublisher
from tools.publishers.csdn_browser import CsdNBrowserPublisher
from tools.publishers.wechat_browser import WeChatBrowserPublisher
from tools.publishers.wechat_api import WeChatApiPublisher

logger = logging.getLogger(__name__)


def build_pipeline(
    observer: Observer,
    claude_client: any,
    publishers: list | None = None,
    enable_judge: bool = True,
    publish_mode: bool = False,
    enabled_platforms: list[str] | None = None,
    stash: dict | None = None,
):
    """Build the full multi-agent pipeline.

    Args:
        stash: mutable dict to capture intermediate outputs (e.g., analyze result)
    """
    if stash is None:
        stash = {}

    # Create agents (each demonstrates a distinct pattern)
    capture_agent = CaptureAgent(observer=observer, claude_client=claude_client)
    analyze_agent = AnalyzeAgent(observer=observer, claude_client=claude_client)

    if enable_judge:
        # Judge loop: Write → Judge ↻ (self-correction loop)
        write_agent = WriteAgent(observer=observer, claude_client=claude_client)
        judge_agent = JudgeAgent(observer=observer, claude_client=claude_client)
        from tools.experience_store import ExperienceStore
        polisher_agent = PolisherAgent(observer=observer, claude_client=claude_client)
        write_stage = JudgeLoopPipeline(
            write_agent=write_agent,
            judge_agent=judge_agent,
            observer=observer,
            max_iterations=3,
            pass_threshold=70,
            experience_store=ExperienceStore(),
            renderer=TemplateRenderer(),
            polisher=polisher_agent,
        )
    else:
        write_stage = WriteAgent(observer=observer, claude_client=claude_client)

    adapt_agent = AdaptAgent(observer=observer, claude_client=claude_client)

    # Publish agent with platform connectors
    publish_agent = PublishAgent(
        publishers=publishers or [],
        observer=observer,
        claude_client=claude_client,
    )

    # Build the pipeline
    orchestrator = PipelineOrchestrator(observer=observer)

    orchestrator.add_stage(
        "capture",
        capture_agent,
        output_transform=lambda data, s=stash: (s.update({"capture": data}) or data),
    )
    orchestrator.add_stage(
        "analyze",
        analyze_agent,
        input_transform=lambda data: sanitize_input(data),
        # Stash analyze output for interview agent
        output_transform=lambda data, s=stash: (s.update({"analyze": data}) or data),
    )

    if enable_judge:
        orchestrator.add_stage(
            "write_judge_loop",
            write_stage,
            # Transform: feed capture+analyze output into write stage
            input_transform=lambda data: {
                "date": data.get("date", ""),
                "day_summary": data.get("day_summary", ""),
                "highlights": data.get("highlights", []),
                "architecture_decisions": data.get("architecture_decisions", []),
                "key_insights": data.get("key_insights", []),
                "tags": data.get("tags", []),
                "themes": data.get("themes", []),
            },
            # Stage 2 — Validate article for privacy before adapt/publish
            output_transform=lambda data: _validate_and_save(data[0] if isinstance(data, tuple) else data),
        )
    else:
        orchestrator.add_stage(
            "write",
            write_stage,
            output_transform=lambda data: _validate_and_save(data),
        )

    # Set up platform targets — only include enabled platforms
    all_platforms = {
        "juejin": {"name": "juejin", "language": "zh", "audience": "Chinese developers (掘金)"},
        "devto": {"name": "devto", "language": "en", "audience": "Global developers (Dev.to)"},
        "csdn": {"name": "csdn", "language": "zh", "audience": "Chinese developers (CSDN)"},
        "wechat_mp": {"name": "wechat_mp", "language": "zh", "audience": "Chinese mobile readers (微信)"},
    }
    enabled_platforms = set(enabled_platforms or [])
    target_platforms = [v for k, v in all_platforms.items() if k in enabled_platforms or not enabled_platforms]

    orchestrator.add_stage(
        "adapt",
        adapt_agent,
        input_transform=lambda data: {
            "article": _extract_article(data),
            "platforms": target_platforms,
        },
        critical=False,  # Adapt can fail without aborting
    )

    orchestrator.add_stage(
        "publish",
        publish_agent,
        input_transform=lambda data: {
            "versions": data.get("versions", []) if isinstance(data, dict) else data,
            "publish": publish_mode,
        },
        critical=False,  # Publish failure doesn't mean pipeline failure
    )

    return orchestrator, stash


def _quick_fix_title(title: str) -> str:
    """Replace placeholder/bad titles with something clickable."""
    import re
    bad_patterns = [
        r"^\d{4}-\d{2}-\d{2}$",         # 日期
        r"^#+$",                          # 纯 #
        r"^###",                          # 章节标题
        r"^日期",                          # 日期开头
        r"^在 202\d",                     # "在202x年的今天"
        r"^今天",                          # "今天在开发"
        r"^最近",                          # "最近在搞"
        r"^作为一名",                       # "作为一名..."
        r"^---",                          # Markdown 分隔线
    ]
    for pat in bad_patterns:
        if re.match(pat, title.strip()):
            return None  # Signal to use fallback
    if len(title.strip()) < 5:
        return None
    return title


_FALLBACK_TITLES = [
    "LLM 输出总崩？一行正则搞定它",
    "还在死磕 Prompt？试试后处理管道",
    "AI 写代码很行，写文档？不行。",
    "生产环境又报警了，这次是因为___",
    "一个 Python 脚本，救了 Markdown 渲染",
    "3 个习惯，让你每天少浪费 30% 的 Token",
    "当 Agent 开始乱说话：一个格式修复实录",
    "放弃调 Prompt 了，我换了个思路",
]


def _validate_and_save(article: dict) -> dict:
    """Validate privacy, save, generate cover. Content already rendered by JudgeLoopPipeline."""
    if isinstance(article, (list, tuple)):
        article = article[0]
    if not isinstance(article, dict):
        logger.error(f"Expected dict article, got {type(article)}")
        return {}

    # Fix bad title
    raw_title = article.get("title", "")
    fixed = _quick_fix_title(raw_title)
    if fixed is None:
        import random
        fallback = random.choice(_FALLBACK_TITLES)
        logger.warning(f"Bad title '{raw_title}' → replaced with '{fallback}'")
        article["title"] = fallback
        article["_title_fixed"] = True

    # Save rendered Markdown
    try:
        path = save_article(article)
        logger.info(f"Article saved: {path}")
    except Exception as e:
        logger.warning(f"Could not save article: {e}")

    # Privacy validation on rendered content
    is_safe, findings = validate_article_safe(article)
    if not is_safe:
        logger.warning(f"⚠️  {len(findings)} potential secrets found")
    else:
        logger.info("✓ Article privacy check passed")

    # Generate cover image
    try:
        cover_path = generate_cover(
            article.get("title", "技术复盘"),
            tags=article.get("tags", []),
        )
        if cover_path:
            article["cover_image"] = cover_path
            logger.info(f"🖼️  Cover generated: {cover_path}")
    except Exception as e:
        logger.warning(f"Cover generation skipped: {e}")

    return article


def _sync_to_obsidian(article: dict) -> None:
    """Copy generated article to Obsidian vault if configured."""
    import os
    import shutil
    from pathlib import Path

    vault_path = None
    # Try to read from settings
    settings_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.yaml")
    if os.path.exists(settings_path):
        try:
            import yaml
            with open(settings_path, "r") as f:
                settings = yaml.safe_load(f) or {}
            vault = settings.get("output", {}).get("obsidian_vault", "")
            if vault:
                vault_path = os.path.expanduser(vault)
        except Exception:
            pass

    if not vault_path or not os.path.isdir(vault_path):
        logger.debug("Obsidian vault not configured or not found — skipping")
        return

    # Generate filename from title
    title = article.get("title", "article")[:30]
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    filename = f"日报_{safe_title}.md"

    # Build content with Obsidian frontmatter
    content = article.get("content", "")
    frontmatter = f"""---
type: daily-dev-log
date: "{datetime.now().strftime("%Y-%m-%d")}"
tags: [{', '.join(article.get('tags', ['dev']))}]
source: agent-daily-publisher
---

"""
    full_content = frontmatter + content

    dest = Path(vault_path) / filename
    with open(dest, "w", encoding="utf-8") as f:
        f.write(full_content)
    logger.info(f"📓 Synced to Obsidian: {dest}")


def _save_interview(data: dict) -> dict:
    """Save interview questions article to data/interviews/."""
    from pathlib import Path

    out_dir = Path(__file__).parent.parent / "data" / "interviews"
    out_dir.mkdir(parents=True, exist_ok=True)

    content = data.get("content", "")
    title = data.get("title", f"面试题日报_{datetime.now().strftime('%Y-%m-%d')}")
    summary = data.get("summary", "")
    q_count = data.get("question_count", 0)

    filename = f"{datetime.now().strftime('%Y-%m-%d')}_面试题_{q_count}道.md"
    filepath = out_dir / filename

    frontmatter = f"""---
title: {title}
date: "{datetime.now().strftime('%Y-%m-%d')}"
type: interview-questions
question_count: {q_count}
difficulty: {data.get('difficulty_levels', [])}
source: agent-daily-publisher
---

"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(frontmatter + content)

    logger.info(f"📝 Interview questions saved ({q_count}q): {filepath}")

    # Also sync to Obsidian if configured
    try:
        _sync_to_obsidian({"title": title, "content": frontmatter + content, "tags": ["interview", "ai"]})
    except Exception:
        pass

    return data


def _save_and_pass(data: dict) -> dict:
    """Save interview output and return the input unchanged for pipeline to continue.

    The pipeline is sequential — interview output must not overwrite the article
    that the adapt stage needs. This wrapper saves the interview result and
    returns the dict as-is (adapt receives the original article data).
    """
    try:
        _save_interview(data)
    except Exception as e:
        logger.warning(f"Interview save failed (non-critical): {e}")
    return data  # unchanged — passes through for next stage


    """Post-process code blocks: fix indentation, missing keywords, spacing."""
    import re

    def _fix_block(match):
        lang = match.group(1) or ""
        code = match.group(2)
        # Fix missing 'catch' before '('
        code = re.sub(r'(?<!\w)(\s*)\((\w+\s+\w+\s*)\)\s*\{', r'\1catch (\2) {', code)
        # Fix inconsistent indentation (normalize to 4 spaces)
        lines = code.split("\n")
        fixed = []
        for line in lines:
            # Replace tabs with spaces
            line = line.replace("\t", "    ")
            # Remove trailing whitespace
            line = line.rstrip()
            fixed.append(line)
        # Remove leading/trailing empty lines
        while fixed and not fixed[0].strip():
            fixed.pop(0)
        while fixed and not fixed[-1].strip():
            fixed.pop()
        # Ensure code blocks have consistent newlines
        result = "\n".join(fixed)
        return f"```{lang}\n{result}\n```"

    # Find and fix all code blocks
    result = re.sub(r'```(\w*)\n(.*?)```', _fix_block, text, flags=re.DOTALL)
    return result


def _clean_code_blocks(text: str) -> str:
    """Post-process code blocks: fix common formatting issues."""
    import re

    def _fix_block(match):
        lang = match.group(1) or ""
        code = match.group(2)
        # Fix missing 'catch' before '('
        code = re.sub(r'(?<!\w)(\s*)\((\w+\s+\w+\s*)\)\s*\{', r'\1catch (\2) {', code)
        # Normalize indentation
        lines = code.split("\n")
        fixed = []
        for line in lines:
            line = line.replace("\t", "    ")
            line = line.rstrip()
            fixed.append(line)
        while fixed and not fixed[0].strip():
            fixed.pop(0)
        while fixed and not fixed[-1].strip():
            fixed.pop()
        return "```" + lang + "\n" + "\n".join(fixed) + "\n```"

    return re.sub(r'```(\w*)\n(.*?)```', _fix_block, text, flags=re.DOTALL)


def _publish_interview(date: str, publishers: list) -> None:
    """Publish interview questions to Dev.to as a separate article."""
    import shutil
    import glob
    from pathlib import Path

    # Find the latest interview file for this date
    interview_dir = Path(__file__).parent.parent / "data" / "interviews"
    pattern = f"{date}_面试题_*"
    files = sorted(interview_dir.glob(pattern))
    if not files:
        logger.debug("No interview file found for publishing")
        return

    content = files[-1].read_text(encoding="utf-8")

    # Strip frontmatter and extract title
    body = content
    title = f"AI Interview Questions - {date}"
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].split("\n"):
                if line.startswith("title:"):
                    title = line.replace("title:", "").strip().strip('"')
                    break
            body = parts[2].strip()

    # Clean code blocks
    body = _clean_code_blocks(body)

    # Publish to Dev.to
    devto = next((p for p in publishers if p.name == "devto"), None)
    if devto and devto.validate_config():
        result = devto.publish(
            title=title,
            content=body,
            tags=["ai", "interview", "career", "agents"],
        )
        if result.success:
            logger.info(f"📤 Interview published to Dev.to: {result.url}")

    # Publish to WeChat MP (as draft)
    wechat = next((p for p in publishers if p.name == "wechat_mp"), None)
    if wechat and wechat.validate_config():
        result = wechat.publish(
            title=f"AI面试题 | {date}",
            content=body,
            tags=["AI", "面试", "技术成长"],
        )
        if result.success:
            logger.info(f"📤 Interview draft saved to WeChat MP: {result.url}")


def _run_usage_analysis(date: str, claude: any, observer: any, stash: dict, state: any) -> None:
    """Analyze Claude Code usage patterns from daily sessions."""
    if state.is_completed("usage_analysis"):
        logger.info("  ⏭️  Usage analysis: skipped (cached)")
        return

    from agents.usage_analysis_agent import UsageAnalysisAgent
    ua = UsageAnalysisAgent(observer=observer, claude_client=claude)
    capture_data = stash.get("capture", {})
    sessions = capture_data.get("sessions", []) if isinstance(capture_data, dict) else []
    analyze_data = stash.get("analyze", {})
    print(f"\n  📊 Analyzing Claude Code usage ({len(sessions)} sessions)...")
    result = ua.run({
        "date": date,
        "sessions": sessions,
        "day_summary": analyze_data.get("day_summary", "") if isinstance(analyze_data, dict) else "",
        "highlights": analyze_data.get("highlights", []) if isinstance(analyze_data, dict) else [],
    })
    _save_usage_analysis(result)
    state.complete_stage("usage_analysis", {"patterns": len(result.get("positive_patterns", []))})
    print(f"  ✓ Usage analysis: {len(result.get('positive_patterns', []))} positives, {len(result.get('negative_patterns', []))} improvements")


def _save_usage_analysis(data: dict) -> None:
    """Save usage analysis report to data/usage/."""
    from pathlib import Path
    out_dir = Path(__file__).parent.parent / "data" / "usage"
    out_dir.mkdir(parents=True, exist_ok=True)
    filepath = out_dir / f"{datetime.now().strftime('%Y-%m-%d')}_claude_usage.md"
    content = data.get("content", "")
    title = data.get("title", "Claude Code 使用分析")
    frontmatter = f"""---
title: {title}
date: "{datetime.now().strftime('%Y-%m-%d')}"
type: usage-analysis
source: agent-daily-publisher
---

"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(frontmatter + content)
    logger.info(f"📊 Usage analysis saved: {filepath}")


def _extract_article(data: dict) -> dict:
    """Extract article from various pipeline stage output formats."""
    if isinstance(data, dict):
        # Direct article output
        if "title" in data and "content" in data:
            return data
        # Nested under 'article' key
        if "article" in data:
            return data["article"]
        # Pipeline result wrapper
        if "final_output" in data:
            return _extract_article(data["final_output"])
    return data


def main():
    parser = argparse.ArgumentParser(description="Agent Daily Publisher")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"),
                       help="Date to process (YYYY-MM-DD)")
    parser.add_argument("--publish", action="store_true",
                       help="Actually publish to platforms (default: dry run)")
    parser.add_argument("--no-judge", action="store_true",
                       help="Skip quality evaluation loop")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s | %(message)s")

    print(f"\n{'='*60}")
    print(f"  Agent Daily Publisher")
    print(f"  Date: {args.date}")
    print(f"  Mode: {'LIVE' if args.publish else 'DRY RUN'}")
    print(f"  Judge: {'OFF' if args.no_judge else 'ON'}")
    print(f"{'='*60}\n")

    # Initialize
    observer = Observer()

    # Initialize Claude client
    try:
        from anthropic import Anthropic
        claude = Anthropic()
        print("  ✓ Claude API client initialized")
    except ImportError:
        print("  ! anthropic SDK not installed. Install with: pip install anthropic")
        print("  ! Using mock client for testing\n")
        claude = _MockClaude()

    # Configure publishers
    publishers = []
    enabled_platforms = set()
    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")

    # Load platform config
    platforms_config = {}
    platforms_path = os.path.join(config_dir, "platforms.yaml")
    if os.path.exists(platforms_path):
        try:
            import yaml
            with open(platforms_path, "r") as f:
                platforms_config = yaml.safe_load(f) or {}
        except Exception:
            pass

    devto_config = platforms_config.get("devto", {})
    juejin_config = platforms_config.get("juejin", {})

    if devto_config.get("enabled", False):
        publishers.append(DevToPublisher(devto_config))
        enabled_platforms.add("devto")
        print("  ✓ Dev.to publisher configured")
    else:
        print("  - Dev.to publisher: disabled (configure in config/platforms.yaml)")

    if juejin_config.get("enabled", False):
        publishers.append(JuejinPublisher(juejin_config))
        enabled_platforms.add("juejin")
        print("  ✓ Juejin publisher configured")
    else:
        print("  - Juejin publisher: disabled (configure in config/platforms.yaml)")

    # Browser-based publishers (no API available)
    csdn_config = platforms_config.get("csdn", {})
    if csdn_config.get("enabled", False):
        publishers.append(CsdNBrowserPublisher(csdn_config))
        enabled_platforms.add("csdn")
        print("  ✓ CSDN browser publisher configured")
    else:
        print("  - CSDN publisher: disabled (browser mode, configure in config/platforms.yaml)")

    wechat_config = platforms_config.get("wechat_mp", {})
    if wechat_config.get("enabled", False):
        # Browser automation is the primary method (no IP whitelist needed)
        # API mode requires fixed IP whitelist — only use if use_api: true
        if wechat_config.get("use_api", False):
            api_pub = WeChatApiPublisher(wechat_config)
            if api_pub.validate_config():
                publishers.append(api_pub)
                print("  ✓ WeChat MP API publisher configured (requires IP whitelist)")
            else:
                print("  ✗ WeChat MP API: AppID/Secret missing, falling back to browser")
                publishers.append(WeChatBrowserPublisher(wechat_config))
                print("  ✓ WeChat MP browser publisher configured")
        else:
            publishers.append(WeChatBrowserPublisher(wechat_config))
            print("  ✓ WeChat MP browser publisher configured (auto-login via saved cookie)")
        enabled_platforms.add("wechat_mp")
    else:
        print("  - WeChat MP publisher: disabled (configure in config/platforms.yaml)")

    print()

    # Build and run pipeline (with resume support)
    from core.state import PipelineState
    pipeline_stash = {}
    from core.state import PipelineState
    pipeline_state = PipelineState(args.date)

    # Check if we can resume from a partial run
    completed = pipeline_state._state.get("completed_stages", [])
    errors = pipeline_state._state.get("errors", {})

    # If everything already done (including interview), skip entirely
    if pipeline_state.is_completed("publish") and pipeline_state.is_completed("interview"):
        pub_results = pipeline_state.get_publish_results()
        if any(r.get("success") for r in pub_results.values()):
            print(f"  ⏭️  Pipeline already completed for {args.date}")
            print(f"  {pipeline_state.summary()}")
            # Still try to publish interview if it hasn't been published
            _publish_interview(args.date, publishers)
            return

    # If there are partial completions, we can resume
    if completed or errors:
        print(f"  🔄 Resuming pipeline for {args.date}")
        print(f"     Already done: {completed}")
        print(f"     Failed: {list(errors.keys())}")

    pipeline_stash = {}
    orchestrator, pipeline_stash = build_pipeline(
        observer=observer,
        claude_client=claude,
        publishers=publishers,
        enable_judge=not args.no_judge,
        publish_mode=args.publish,
        enabled_platforms=list(enabled_platforms),
        stash=pipeline_stash,
    )

    # Run
    print("  🚀 Running pipeline...\n")
    result = orchestrator.run({"date": args.date}, pipeline_state=pipeline_state)

    # Output results
    print(f"\n{'='*60}")
    print(f"  Pipeline {'SUCCEEDED' if result.success else 'COMPLETED WITH ERRORS'}")
    print(f"  Duration: {result.duration:.1f}s")
    print(f"{'='*60}\n")

    for stage in result.stages:
        status = "✓" if not stage.get("error") else "✗"
        print(f"  {status} {stage['name']}: {stage.get('duration', 0):.1f}s")
        if stage.get("error"):
            print(f"    Error: {stage['error']}")

    # Print publish summary
    if result.final_output and isinstance(result.final_output, dict):
        summary = result.final_output.get("summary", "")
        if summary:
            print(f"\n  📋 Summary: {summary}")

        results_list = result.final_output.get("results", [])
        if results_list:
            print(f"\n  📤 Publishing Results:")
            for r in results_list:
                status = "✓" if r.get("success") else "✗"
                url = r.get("url", "")
                error = r.get("error", "")
                print(f"    {status} {r['platform']}: {url or error}")

    # Save observer log
    print(f"\n  💾 Trace log saved to data/traces/")

    # Run interview question generator (cached via pipeline_state)
    if result.success:
        if not pipeline_state.is_completed("interview"):
            try:
                from agents.interview_agent import InterviewAgent
                ia = InterviewAgent(observer=observer, claude_client=claude)
                analyze_data = pipeline_stash.get("analyze", {})
                interview_data = {
                    "date": args.date,
                    "day_summary": analyze_data.get("day_summary", ""),
                    "highlights": analyze_data.get("highlights", []),
                    "architecture_decisions": analyze_data.get("architecture_decisions", []),
                    "key_insights": analyze_data.get("key_insights", []),
                    "tags": analyze_data.get("tags", []),
                }
                print(f"\n  🎯 Generating interview questions...")
                interview_result = ia.run(interview_data)
                _save_interview(interview_result)
                pipeline_state.complete_stage("interview", {"count": interview_result.get("question_count", 0)})
                print(f"  ✓ Interview questions: {interview_result.get('question_count', 0)} questions")
            except Exception as e:
                print(f"  - Interview questions skipped: {e}")
        else:
            print(f"  ⏭️  Interview questions: skipped (cached)")

        # Publish interview to Dev.to if there's a matching publisher
        try:
            _publish_interview(args.date, publishers)
        except Exception as e:
            print(f"  - Interview publish skipped: {e}")

        # Claude Code Usage Analysis
        try:
            _run_usage_analysis(args.date, claude, observer, pipeline_stash, pipeline_state)
        except Exception as e:
            print(f"  - Usage analysis skipped: {e}")

    return result


class _MockClaude:
    """Minimal mock for testing without API keys."""

    class Messages:
        def create(self, **kwargs):
            class MockResponse:
                class Content:
                    type = "text"
                    text = '{"status": "mock", "message": "This is a mock response. Configure ANTHROPIC_API_KEY for real output."}'

                class Usage:
                    input_tokens = 0
                    output_tokens = 0

                def __init__(self):
                    self.content = [self.Content()]
                    self.usage = self.Usage()

            return MockResponse()

    def __init__(self):
        self.messages = self.Messages()


if __name__ == "__main__":
    main()
