#!/usr/bin/env python3
"""
Structure Replay Engine v1.0 - CLI Entry Point

Usage:
  python run_replay.py                          # Full replay + audit
  python run_replay.py --tf 1h                  # Single TF replay
  python run_replay.py --breakpoint 1783267200  # Breakpoint at timestamp
  python run_replay.py --query-trades BULLISH   # Query trades by direction
"""
import argparse
import logging
import sys
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Structure Replay Engine v1.0")
    parser.add_argument("--data-dir", default="data/multi_tf_state")
    parser.add_argument("--output-dir", default="data/replay_output")
    parser.add_argument("--tf", type=str, help="Filter by timeframe")
    parser.add_argument("--breakpoint", type=int, help="Breakpoint at timestamp")
    parser.add_argument("--query-trades", type=str, help="Query trades by direction")
    parser.add_argument("--query-lines", type=str, help="Query lines by TF")
    args = parser.parse_args()

    from replay_engine.replay_storage import ReplayStorage
    from replay_engine.replay_builder import ReplayBuilder
    from replay_engine.replay_timeline import ReplayTimeline
    from replay_engine.replay_validator import ReplayValidator
    from replay_engine.replay_query import ReplayQueryEngine
    from replay_engine.replay_output import ReplayOutput
    from replay_engine.models import ReplayEvent

    # 1. Load data
    storage = ReplayStorage(args.data_dir)
    storage.build_index()

    # 2. Build replay objects
    builder = ReplayBuilder(storage)
    lines = builder.build_all_lines()
    waves = builder.build_all_waves()
    trades = builder.build_all_trades()
    snapshots = builder.build_snapshots()
    trend_transitions = builder.build_trend_transitions()
    stack_transitions = builder.build_stack_transitions()

    # 3. Build timeline
    timeline = ReplayTimeline()
    for line in lines:
        timeline.add_events(line.lifecycle_history)
    for wave in waves:
        timeline.add_events(wave.lifecycle_history)
    for trade in trades:
        timeline.add_events(trade.lifecycle_history)
    timeline.add_events(trend_transitions)
    timeline.add_events(stack_transitions)
    river_events = storage.get_river_events()
    for evt in river_events:
        timeline.add_event(ReplayEvent(
            timestamp=evt.get("ts", 0),
            event_type=evt.get("event", ""),
            object_type=evt.get("object", ""),
            object_id=evt.get("id", ""),
            lifecycle="UPDATED",
            timeframe=evt.get("tf", ""),
            data=evt.get("data", {}),
        ))
    timeline.sort()

    # 4. Validate
    validator = ReplayValidator()
    audit = validator.validate(timeline, lines, waves, trades)
    clock_sync = timeline.validate_clock_sync()

    # 5. Query engine
    query = ReplayQueryEngine(timeline, lines, waves, trades, snapshots)

    # 6. Handle CLI commands
    if args.breakpoint:
        bp = query.get_breakpoint(args.breakpoint)
        print(json.dumps(bp, indent=2, default=str))
        return

    if args.query_trades:
        results = query.query_trades(direction=args.query_trades)
        print(json.dumps([t.to_dict() for t in results], indent=2, default=str))
        return

    if args.query_lines:
        results = query.query_lines(timeframe=args.query_lines)
        print(json.dumps([l.to_dict() for l in results], indent=2, default=str))
        return

    # 7. Full replay export
    output = ReplayOutput(args.output_dir)
    report = query.get_full_report()
    output.export_all(timeline.to_list(), report, audit)

    # 8. Print summary
    print("\n" + "=" * 60)
    print("  STRUCTURE REPLAY ENGINE v1.1 - CERTIFICATION")
    print("=" * 60)
    print(f"  Events:     {audit.total_events}")
    print(f"  Lines:      {audit.total_lines}")
    print(f"  Waves:      {audit.total_waves}")
    print(f"  Trades:     {audit.total_trades}")
    print(f"  Transitions:{len(trend_transitions) + len(stack_transitions)}")
    print(f"  River Evts: {len(river_events)}")
    print(f"  Clock Sync: {clock_sync['sync_issues']} issues")
    print(f"  Consistency:{audit.consistency_score:.4f}")
    print(f"  Certification: {audit.certification}")
    if audit.issues:
        print(f"  Issues:     {', '.join(audit.issues)}")
    print("=" * 60)
    print(f"  Output: {args.output_dir}/")
    print("=" * 60)

    storage.shutdown()


if __name__ == "__main__":
    main()
