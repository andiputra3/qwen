"""
Replay Output - POST-AUDIT FIXED VERSION
Fix P2-3: Streaming export for large timelines
"""
import json
import logging
from pathlib import Path
from typing import Dict, List
from replay_engine.models import ReplayAuditResult

logger = logging.getLogger(__name__)


class ReplayOutput:
    def __init__(self, output_dir: str = "data/replay_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_timeline(self, timeline_data: List[dict], filename: str = "replay_timeline.json"):
        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            json.dump(timeline_data, f, indent=2, default=str)
        logger.info(f"[REPLAY-OUTPUT] Timeline exported: {filepath}")

    def export_timeline_streaming(self, timeline_data: List[dict],
                                   chunk_size: int = 1000,
                                   base_filename: str = "replay_timeline"):
        total = len(timeline_data)
        if total <= chunk_size:
            self.export_timeline(timeline_data, f"{base_filename}.json")
            return

        num_chunks = (total + chunk_size - 1) // chunk_size
        manifest = {"total_events": total, "chunks": num_chunks, "chunk_size": chunk_size, "files": []}

        for i in range(num_chunks):
            start = i * chunk_size
            end = min(start + chunk_size, total)
            chunk_file = f"{base_filename}_part{i+1:03d}.json"
            filepath = self.output_dir / chunk_file
            with open(filepath, "w") as f:
                json.dump(timeline_data[start:end], f, indent=2, default=str)
            manifest["files"].append(chunk_file)

        with open(self.output_dir / f"{base_filename}_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"[REPLAY-OUTPUT] Timeline exported in {num_chunks} chunks")

    def export_report(self, report: Dict, filename: str = "replay_report.json"):
        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"[REPLAY-OUTPUT] Report exported: {filepath}")

    def export_audit(self, audit: ReplayAuditResult, filename: str = "replay_audit.json"):
        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            json.dump(audit.to_dict(), f, indent=2, default=str)
        logger.info(f"[REPLAY-OUTPUT] Audit exported: {filepath}")

    def export_all(self, timeline_data, report, audit):
        self.export_timeline_streaming(timeline_data)
        self.export_report(report)
        self.export_audit(audit)
        logger.info(f"[REPLAY-OUTPUT] All exports complete: {self.output_dir}")
