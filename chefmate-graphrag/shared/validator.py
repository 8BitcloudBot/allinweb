import difflib
from typing import List, Set, Optional
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    is_valid: bool = True
    hallucinated_dishes: List[str] = field(default_factory=list)
    confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)


class AnswerValidator:
    def __init__(self):
        self.valid_dishes: Set[str] = set()

    def load_valid_dishes(self, names: List[str]):
        self.valid_dishes = set(names)

    def validate_answer(self, answer: str, evidence_dishes: List[str]) -> ValidationResult:
        mentioned = self._extract_dish_names(answer)
        warnings = []
        hallucinated = []

        for dish in mentioned:
            if dish not in evidence_dishes and dish not in self.valid_dishes:
                hallucinated.append(dish)
                close = self.fuzzy_match_unknown(dish)
                if close:
                    warnings.append(f"'{dish}' may be '{close}'")

        return ValidationResult(
            is_valid=len(hallucinated) == 0,
            hallucinated_dishes=hallucinated,
            confidence=1.0 - (len(hallucinated) / max(len(mentioned), 1)),
            warnings=warnings,
        )

    def _extract_dish_names(self, text: str) -> List[str]:
        found = []
        for name in self.valid_dishes:
            if len(name) >= 2 and name in text:
                found.append(name)
        return found

    def fuzzy_match_unknown(self, name: str) -> Optional[str]:
        matches = difflib.get_close_matches(name, self.valid_dishes, n=1, cutoff=0.75)
        return matches[0] if matches else None
