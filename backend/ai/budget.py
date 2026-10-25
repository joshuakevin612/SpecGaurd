"""A deadline and conservative aggregate token budget shared by all model steps."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import monotonic

CURRENT = ContextVar('specguard_budget', default=None)


@dataclass
class Budget:
    deadline: float
    calls: int = 0
    reserved_tokens: int = 0

    def reserve(self, input_chars, output_tokens):
        from .provider import ProviderError
        self.calls += 1
        # Four tokens per Unicode character bounds UTF-8 byte fallback tokenizers
        # conservatively; this is a hard work budget, not a billing estimate.
        self.reserved_tokens += 4 * input_chars + output_tokens
        if self.calls > 10 or self.reserved_tokens > 200000 or self.remaining() <= 0:
            raise ProviderError('Verification budget exhausted; no further model call was made')

    def remaining(self):
        return max(0, self.deadline - monotonic())


@contextmanager
def run_budget(seconds=140):
    budget = Budget(monotonic() + seconds)
    token = CURRENT.set(budget)
    try:
        yield budget
    finally:
        CURRENT.reset(token)
