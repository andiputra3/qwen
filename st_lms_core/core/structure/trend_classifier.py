"""
Trend Classifier - Official Market State Classifier (CONSTITUTIONAL C008)

TANGGUNG JAWAB: Mengklasifikasikan MARKET STATE dari StructuralForm.
Hanya 3 state valid: UPTREND, DOWNTREND, SIDEWAY.
SIDEWAY = hasil klasifikasi struktur (CONVERGING/FLAT/CHAOTIC/NO_STRUCTURE/SINGLE).
TIDAK menggunakan ATR, MACD, OI, atau indikator apa pun.
"""
import logging

from st_lms_core.core.models.market_state import MarketState, StructuralForm

logger = logging.getLogger(__name__)


class TrendClassifier:
    FORM_TO_STATE = {
        StructuralForm.ASCENDING_STAIRS: MarketState.UPTREND,
        StructuralForm.DESCENDING_STAIRS: MarketState.DOWNTREND,
        StructuralForm.CONVERGING: MarketState.SIDEWAY,
        StructuralForm.FLAT_CORRIDOR: MarketState.SIDEWAY,
        StructuralForm.SINGLE_DIRECTION: MarketState.SIDEWAY,
        StructuralForm.CHAOTIC: MarketState.SIDEWAY,
        StructuralForm.NO_STRUCTURE: MarketState.SIDEWAY,
    }

    def classify(self, structural_form: StructuralForm) -> MarketState:
        state = self.FORM_TO_STATE.get(structural_form, MarketState.SIDEWAY)
        logger.debug(f"[TREND-CLASSIFIER] Form={structural_form.value} -> State={state.value}")
        return state

    def reset(self) -> None:
        pass
