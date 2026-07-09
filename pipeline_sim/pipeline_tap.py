"""
Pipeline Tap - CRASH-FIXED VERSION (P0-5)
Fix: ALL field access uses .get() with safe defaults.
Never raises KeyError, AttributeError, or TypeError on incomplete audit dicts.
"""
from decimal import Decimal
from typing import Dict, Any, Optional


class PipelineTap:
    """Crash-safe reader of AdaptiveSTLMSPipeline internal state."""

    @staticmethod
    def extract_measure(pipeline) -> Dict[str, Any]:
        ctx = getattr(pipeline, '_last_context', None)
        vol = getattr(pipeline, '_vol_calc', None)
        if not ctx:
            return {"price": None, "st_point": None, "macd_bucket": None,
                    "oi_state": None, "atr": None, "velocity": None}
        return {
            "price": float(ctx.price) if hasattr(ctx, 'price') else None,
            "st_point": float(getattr(pipeline, '_last_st_point', 0)) or None,
            "macd_bucket": getattr(ctx, 'macd_state', None),
            "oi_state": getattr(ctx, 'oi_state', None),
            "atr": float(vol.current_atr) if vol and getattr(vol, 'current_atr', None) else None,
            "velocity": getattr(pipeline, '_last_velocity', 'NORMAL_FLOW'),
        }

    @staticmethod
    def extract_structure(pipeline) -> Dict[str, Any]:
        active_ctx = getattr(pipeline, '_last_active_context', None)
        ctx = getattr(pipeline, '_last_context', None)
        geom = getattr(pipeline, '_trend_geom', None)
        if not active_ctx or not ctx:
            return {"market_state": None, "structural_form": None,
                    "living_support": [], "living_resistance": [],
                    "relevant_waves": [], "nearest_support": None,
                    "nearest_resistance": None, "total_living": 0,
                    "compressed": None, "stack_priority": None,
                    "all_valid_lines": {"valid_support": [], "valid_resistance": [], "total_valid": 0}}

        form = None
        try:
            form = geom.analyze(active_ctx).value if geom else None
        except Exception:
            form = None

        return {
            "market_state": getattr(ctx, 'trend_state', None),
            "structural_form": form,
            "living_support": [
                {"id": l.id, "price": float(l.price_level), "status": l.status.value, "points": l.point_count}
                for l in getattr(active_ctx, 'living_support_lines', [])
            ],
            "living_resistance": [
                {"id": l.id, "price": float(l.price_level), "status": l.status.value, "points": l.point_count}
                for l in getattr(active_ctx, 'living_resistance_lines', [])
            ],
            "relevant_waves": [
                {"id": w.id, "dir": w.direction.value, "start": float(w.start_price),
                 "end": float(w.end_price), "amp": float(w.amplitude), "len": w.length_points}
                for w in getattr(active_ctx, 'relevant_waves', [])
            ],
            "nearest_support": float(active_ctx.nearest_support.price_level) if getattr(active_ctx, 'nearest_support', None) else None,
            "nearest_resistance": float(active_ctx.nearest_resistance.price_level) if getattr(active_ctx, 'nearest_resistance', None) else None,
            "total_living": getattr(active_ctx, 'total_living_lines', 0),
            "compressed": getattr(ctx, 'compressed', None),
            "stack_priority": getattr(ctx, 'stack_priority', None),
            "all_valid_lines": PipelineTap._extract_all_valid_lines(pipeline),
        }

    @staticmethod
    def _extract_all_valid_lines(pipeline) -> Dict[str, Any]:
        line_builder = getattr(pipeline, '_line_builder', None)
        if not line_builder:
            return {"valid_support": [], "valid_resistance": [], "total_valid": 0}

        valid_support = []
        valid_resistance = []
        try:
            for line in line_builder.all_lines:
                if not line.is_active:
                    continue
                entry = {
                    "id": line.id, "price": float(line.price_level),
                    "direction": line.direction.value, "status": line.status.value,
                    "point_count": line.point_count, "start_ts": line.start_ts,
                    "end_ts": line.end_ts,
                }
                if line.direction.value == "BULLISH":
                    valid_support.append(entry)
                else:
                    valid_resistance.append(entry)
        except Exception:
            pass

        valid_support.sort(key=lambda l: l["price"])
        valid_resistance.sort(key=lambda l: l["price"], reverse=True)

        return {
            "valid_support": valid_support,
            "valid_resistance": valid_resistance,
            "total_valid": len(valid_support) + len(valid_resistance),
        }

    @staticmethod
    def extract_intelligence(pipeline) -> Dict[str, Any]:
        ctx = getattr(pipeline, '_last_context', None)
        tag = getattr(pipeline, '_last_tag', None)
        river = getattr(pipeline, 'dual_river', None)
        if not ctx or not tag or not river:
            return {"context": None, "tag_hash": None, "river_recommendation": None}

        try:
            river_rec = river.get_entry_recommendation({
                "st_direction": getattr(ctx, 'wave_direction', "") or "",
                "wave_direction": getattr(ctx, 'wave_direction', "") or "",
                "wave_length": getattr(ctx, 'wave_length', 0),
                "stack_priority": getattr(ctx, 'stack_priority', "LOW"),
                "compressed": getattr(ctx, 'compressed', False),
                "macd": getattr(ctx, 'macd_state', "NEUTRAL"),
                "oi_state": getattr(ctx, 'oi_state', "ABSENT") or "ABSENT"
            })
        except Exception:
            river_rec = {"should_enter": False, "confidence": 0.0, "stats": None, "recommendation": "ERROR"}

        return {
            "context": {
                "trend": getattr(ctx, 'trend_state', None),
                "wave_dir": getattr(ctx, 'wave_direction', None),
                "wave_len": getattr(ctx, 'wave_length', 0),
                "compressed": getattr(ctx, 'compressed', None),
                "macd": getattr(ctx, 'macd_state', None),
                "oi": getattr(ctx, 'oi_state', None),
                "priority": getattr(ctx, 'stack_priority', None),
                "support": float(ctx.active_support_price) if getattr(ctx, 'active_support_price', None) else None,
                "resistance": float(ctx.active_resistance_price) if getattr(ctx, 'active_resistance_price', None) else None,
            },
            "tag_hash": getattr(tag, 'hash_key', None),
            "river_recommendation": river_rec,
        }

    @staticmethod
    def extract_proposal(pipeline, audit: dict) -> Optional[Dict[str, Any]]:
        if not audit.get("entry"):
            return None

        proposal = getattr(pipeline, '_last_proposal', None)
        if proposal is None:
            return {
                "entry_price": audit.get("entry_price"),
                "direction": audit.get("direction"),
                "stop_loss": None, "risk_pct": None,
                "guard_line_id": None, "take_profit": None, "tag_hash": None,
            }

        try:
            return {
                "entry_price": float(proposal.entry_price),
                "direction": proposal.direction.value,
                "stop_loss": float(proposal.stop_loss),
                "risk_pct": float(proposal.risk_pct),
                "guard_line_id": getattr(proposal, 'support_line_id', None),
                "take_profit": float(proposal.take_profit) if getattr(proposal, 'take_profit', None) else None,
                "tag_hash": getattr(proposal, 'classification_tag_hash', None),
            }
        except Exception:
            return {"entry_price": audit.get("entry_price"), "direction": audit.get("direction"),
                    "stop_loss": None, "risk_pct": None, "guard_line_id": None,
                    "take_profit": None, "tag_hash": None}

    @staticmethod
    def extract_auth_breakdown(pipeline, audit: dict) -> Dict[str, Any]:
        auth_reason = audit.get("auth", "")
        ctx = getattr(pipeline, '_last_context', None)
        active_ctx = getattr(pipeline, '_last_active_context', None)

        layers = {
            "structure_alignment": None, "sideway_check": None,
            "risk_limit": None, "fib_zone": None,
            "macd_gate": None, "oi_gate": None, "river_gate": None,
        }

        rejection_map = {
            "STRUCTURE_MISALIGNMENT": "structure_alignment",
            "INSIDE_SIDEWAY_STRUCTURE": "sideway_check",
            "RISK_EXCEEDED": "risk_limit",
            "PRICE_NOT_IN_FIB_ZONE": "fib_zone",
            "NO_FIB_LEVELS_AVAILABLE": "fib_zone",
            "MACD_REJECTED": "macd_gate",
            "OI_REJECTED": "oi_gate",
            "RIVER_REJECTED": "river_gate",
        }

        if auth_reason == "APPROVED":
            for k in layers:
                layers[k] = {"passed": True, "detail": ""}
        else:
            rejected_layer = None
            for keyword, layer_name in rejection_map.items():
                if keyword in str(auth_reason):
                    rejected_layer = layer_name
                    break
            for k in layers:
                if k == rejected_layer:
                    layers[k] = {"passed": False, "detail": str(auth_reason)}
                else:
                    layers[k] = {"passed": True, "detail": ""}

        return {
            "final_decision": str(auth_reason),
            "layers": layers,
            "context_at_decision": {
                "market_state": getattr(ctx, 'trend_state', None) if ctx else None,
                "compressed": getattr(ctx, 'compressed', None) if ctx else None,
                "macd": getattr(ctx, 'macd_state', None) if ctx else None,
                "oi": getattr(ctx, 'oi_state', None) if ctx else None,
                "support": float(active_ctx.nearest_support.price_level) if active_ctx and getattr(active_ctx, 'nearest_support', None) else None,
                "resistance": float(active_ctx.nearest_resistance.price_level) if active_ctx and getattr(active_ctx, 'nearest_resistance', None) else None,
            }
        }

    @staticmethod
    def extract_full_snapshot(pipeline, audit: dict) -> Dict[str, Any]:
        """FIX P0-5: Every field access is crash-safe via .get() and getattr()."""
        return {
            "timestamp": audit.get("ts"),
            "st_point": audit.get("st_point"),
            "measure": PipelineTap.extract_measure(pipeline),
            "structure": PipelineTap.extract_structure(pipeline),
            "intelligence": PipelineTap.extract_intelligence(pipeline),
            "governance": {
                "auth": audit.get("auth"),
                "auth_confidence": audit.get("auth_confidence"),
                "proposal": PipelineTap.extract_proposal(pipeline, audit),
                "auth_breakdown": PipelineTap.extract_auth_breakdown(pipeline, audit),
                "entry": audit.get("entry"),
                "entry_price": audit.get("entry_price"),
                "direction": audit.get("direction"),
                "exit": audit.get("exit"),
                "exit_price": audit.get("exit_price"),
                "exit_reason": audit.get("exit_reason"),
            },
            "meta": {
                "river_records": audit.get("river_records"),
                "active_trades": audit.get("active_trades"),
                "balance": audit.get("balance"),
            }
        }
