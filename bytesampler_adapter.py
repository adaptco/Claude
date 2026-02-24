"""
ByteSampler Adapter for avatar.controlbus.synthetic.engineer.v1

Implements exact byte-level sampling using Valid Covering Tree algorithm.
Provides tokenizer-agnostic deterministic sampling for music video generation.
"""

import hashlib
import logging
import random
import secrets
from collections import defaultdict, deque
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

log = logging.getLogger(__name__)

# Maximum bytes a single token may overshoot the target prefix.
_MAX_TOKEN_BYTE_OVERSHOOT = 20
# Safety cap on the number of VCT paths explored per call.
_MAX_VCT_PATHS = 5_000


@dataclass
class TokenPath:
    """Represents a valid token sequence in the covering tree"""
    tokens: List[str]
    bytes_covered: bytes
    probability: float
    overshoot_bytes: bytes  # Bytes beyond the target prefix

    def next_bytes(self, prefix: bytes) -> bytes:
        """Return the next bytes after the prefix"""
        full_bytes = self.bytes_covered
        if full_bytes.startswith(prefix):
            return full_bytes[len(prefix):]
        return b''


@dataclass
class ByteDistribution:
    """Byte-level probability distribution"""
    distributions: Dict[bytes, float]  # byte_continuation -> probability
    entropy: float
    total_paths: int

    def sample(self, rng_seed: int) -> bytes:
        """Sample from distribution deterministically"""
        rng = random.Random(rng_seed)

        # Convert to sorted list for determinism
        items = sorted(self.distributions.items())
        bytes_seq = [b for b, _ in items]
        probs = [p for _, p in items]

        # Normalize probabilities
        total = sum(probs)
        if total == 0:
            return b''
        probs = [p / total for p in probs]

        # Deterministic sample
        return rng.choices(bytes_seq, weights=probs, k=1)[0]


class ValidCoveringTree:
    """
    Builds the tree of all valid token sequences whose concatenated bytes
    match a given byte prefix and overshoot by at most one token.
    """

    def __init__(self, tokenizer_type: str):
        self.tokenizer_type = tokenizer_type
        # Mock tokenizer vocab for demonstration
        # In production, load actual tokenizer
        self.vocab = self._init_vocab(tokenizer_type)

    def _init_vocab(self, tokenizer_type: str) -> Dict[str, bytes]:
        """Initialize tokenizer vocabulary"""
        if tokenizer_type == "bpe":
            # Mock BPE tokens
            return {
                "<|begin|>": b"",
                "Generate": b"Generate",
                " ambient": b" ambient",
                " music": b" music",
                " with": b" with",
                " crystal": b" crystal",
                "\n": b"\n",
                "cici": b"cici",
                "_cp": b"_cp",
                "001": b"001",
                "test": b"test",
            }
        if tokenizer_type == "sentencepiece":
            # Mock sentencepiece tokens
            return {
                "▁Generate": b" Generate",
                "▁ambient": b" ambient",
                "▁music": b" music",
                "▁crystal": b" crystal",
                "ci": b"ci",
                "ci_": b"ci_",
                "c": b"c",
                "i": b"i",
                "cp": b"cp",
                "001": b"001",
            }
        raise ValueError(f"Unknown tokenizer type: {tokenizer_type}")

    def build_tree(self,
                   byte_prefix: bytes,
                   max_tokens: int = 10) -> List[TokenPath]:
        """
        Build Valid Covering Tree for byte_prefix.

        Returns all valid token sequences that:
        1. Concatenate to bytes starting with byte_prefix
        2. Overshoot by at most 1 token
        """
        paths = []

        def explore(current_tokens: List[str],
                   current_bytes: bytes,
                   depth: int):
            """Recursively explore valid token paths"""
            if depth > max_tokens:
                return

            # Check if we've covered the prefix
            if current_bytes.startswith(byte_prefix):
                overshoot = current_bytes[len(byte_prefix):]
                # Allow overshoot of at most one token's worth
                if len(overshoot) <= _MAX_TOKEN_BYTE_OVERSHOOT:
                    paths.append(TokenPath(
                        tokens=current_tokens.copy(),
                        bytes_covered=current_bytes,
                        probability=1.0,  # Will be computed later
                        overshoot_bytes=overshoot
                    ))
                    if len(paths) >= _MAX_VCT_PATHS:
                        return  # Safety cap reached
                    # Don't return - allow exploring further

            # If we've already overshot too much, stop this branch
            if len(current_bytes) > len(byte_prefix) + _MAX_TOKEN_BYTE_OVERSHOOT:
                return

            # Explore adding each token
            for token_text, token_bytes in self.vocab.items():
                if token_text == "<|begin|>":
                    continue  # Skip special tokens in middle

                new_bytes = current_bytes + token_bytes
                # Pruning: If new_bytes can't possibly lead to prefix, skip
                if not byte_prefix.startswith(new_bytes[:len(byte_prefix)]) and \
                   not new_bytes.startswith(byte_prefix[:len(new_bytes)]):
                    continue

                explore(
                    current_tokens + [token_text],
                    new_bytes,
                    depth + 1
                )

        # Start exploration
        explore([], b"", 0)

        return paths

    def compute_probabilities(self,
                            paths: List[TokenPath],
                            logits_fn: callable) -> List[TokenPath]:
        """
        Compute probability for each path using model logits.

        Args:
            paths: Token paths from build_tree
            logits_fn: Function that returns logits for tokens given prefix
                      signature: (token_prefix: List[str]) -> Dict[str, float]
        """
        for path in paths:
            # Compute path probability as product of token probabilities
            path_prob = 1.0
            for i, token in enumerate(path.tokens):
                prefix_tokens = path.tokens[:i]
                logits = logits_fn(prefix_tokens)

                # Convert logits to probabilities
                token_probs = softmax(logits)
                path_prob *= token_probs.get(token, 1e-10)

            path.probability = path_prob

        return paths


class ByteSamplerAdapter:
    """
    Main ByteSampler adapter implementing exact byte-level sampling.
    """

    def __init__(self,
                 model_endpoint: str,
                 tokenizer_type: str = "bpe",
                 rng_seed: Optional[int] = None):
        self.model_endpoint = model_endpoint
        self.tokenizer_type = tokenizer_type
        self.current_seed = rng_seed if rng_seed is not None else self._generate_seed()
        self.vct = ValidCoveringTree(tokenizer_type)

        # State tracking
        self.history: deque[Tuple[bytes, bytes]] = deque(maxlen=1_000)  # (prefix, sampled_bytes)

    def _generate_seed(self) -> int:
        """Generate a cryptographically random 64-bit seed."""
        return secrets.randbits(64)

    def sample_next_bytes(self,
                         byte_prefix: bytes,
                         constraints: Optional[Dict] = None,
                         max_length: int = 1) -> bytes:
        """Sample next bytes using Valid Covering Tree.

        Args:
            byte_prefix: Current byte prefix
            constraints: Reserved for future constitutional constraint filtering.
            max_length: Maximum bytes to sample

        Returns:
            Sampled bytes continuation
        """
        del constraints  # Reserved — not yet consumed by this implementation
        # Build Valid Covering Tree
        paths = self.vct.build_tree(byte_prefix)

        if not paths:
            raise ValueError(
                f"No valid token paths found for prefix (length={len(byte_prefix)}): "
                f"{byte_prefix[:20]!r}{'...' if len(byte_prefix) > 20 else ''}"
            )

        # Compute probabilities (mock for now)
        paths = self._compute_mock_probabilities(paths)

        # Get byte-level distribution
        dist = self.get_distribution_from_paths(paths, byte_prefix)

        # Sample
        sampled = dist.sample(self.current_seed)

        # Update state
        self.history.append((byte_prefix, sampled))
        self.current_seed = self._derive_next_seed(self.current_seed, sampled)

        return sampled[:max_length]

    def get_distribution(self, byte_prefix: bytes) -> ByteDistribution:
        """
        Get exact byte-level distribution for prefix.

        Returns:
            ByteDistribution with exact probabilities
        """
        paths = self.vct.build_tree(byte_prefix)
        paths = self._compute_mock_probabilities(paths)
        return self.get_distribution_from_paths(paths, byte_prefix)

    def get_distribution_from_paths(self,
                                   paths: List[TokenPath],
                                   byte_prefix: bytes) -> ByteDistribution:
        """
        Marginalize token paths into byte-level distribution.

        This is the core of ByteSampler: aggregate probabilities over all
        valid token sequences that lead to the same byte continuation.
        """
        # Group paths by their next bytes after prefix
        byte_probs = defaultdict(float)

        for path in paths:
            next_bytes = path.next_bytes(byte_prefix)
            if next_bytes:
                byte_probs[next_bytes] += path.probability

        # Normalize
        total_prob = sum(byte_probs.values())
        if total_prob > 0:
            byte_probs = {b: p / total_prob for b, p in sorted(byte_probs.items())}

        # Compute entropy
        entropy = -sum(p * np.log2(p) for p in byte_probs.values() if p > 0)

        return ByteDistribution(
            distributions=dict(byte_probs),
            entropy=entropy,
            total_paths=len(paths)
        )

    def marginalize_tokens(self, byte_prefix: bytes) -> List[TokenPath]:
        """Return all valid token sequences covering prefix"""
        paths = self.vct.build_tree(byte_prefix)
        return self._compute_mock_probabilities(paths)

    def _compute_mock_probabilities(self, paths: List[TokenPath]) -> List[TokenPath]:
        """
        Stub probability computation.

        WARNING: This does NOT call the real model endpoint. It assigns
        random uniform probabilities for local testing only. Replace with
        a real implementation that queries ``self.model_endpoint`` before
        shipping to production.
        """
        log.warning(
            "_compute_mock_probabilities called — model_endpoint '%s' is NOT being queried.",
            self.model_endpoint,
        )
        rng = random.Random(12345)
        
        # Sort paths for determinism
        paths.sort(key=lambda p: p.bytes_covered)

        for path in paths:
            path.probability = rng.random()

        # Normalize
        total = sum(p.probability for p in paths)
        if total > 0:
            for path in paths:
                path.probability /= total

        return paths

    def _derive_next_seed(self, current_seed: int, sampled_bytes: bytes) -> int:
        """Derive next seed deterministically from current seed + sampled bytes"""
        combined = f"{current_seed}:{sampled_bytes.hex()}"
        return int.from_bytes(
            hashlib.sha256(combined.encode()).digest()[:8],
            byteorder='big'
        )

    def get_state(self) -> Dict[str, Any]:
        """Return current ByteSampler state"""
        return {
            "current_seed": self.current_seed,
            "tokenizer_type": self.tokenizer_type,
            "history_length": len(self.history),
            "last_prefix": self.history[-1][0].hex() if self.history else None,
            "last_sampled": self.history[-1][1].hex() if self.history else None
        }


def softmax(logits: Dict[str, float]) -> Dict[str, float]:
    """Apply softmax to logits. Order-stable across dict iteration."""
    keys = list(logits.keys())
    values = np.array([logits[k] for k in keys], dtype=np.float64)
    exp_values = np.exp(values - np.max(values))  # Numerical stability
    probs = exp_values / np.sum(exp_values)
    return dict(zip(keys, probs.tolist()))


def _demo() -> None:
    """Demonstrate ByteSampler adapter usage."""
    print("ByteSampler Adapter Demo\n")

    # Initialize adapter
    demo_adapter = ByteSamplerAdapter(
        model_endpoint="https://api.example.com/v1/generate",
        tokenizer_type="bpe",
        rng_seed=42
    )

    # Example 1: Sample from byte prefix
    demo_prefix = b"Generate ambient music"
    print(f"Prefix: {demo_prefix.decode()}")

    # Get distribution
    demo_dist = demo_adapter.get_distribution(demo_prefix)
    print("\nByte-level distribution:")
    print(f"  Entropy: {demo_dist.entropy:.3f} bits")
    print(f"  Total paths: {demo_dist.total_paths}")
    print("  Continuations:")
    for byte_seq, prob in sorted(demo_dist.distributions.items(), key=lambda x: -x[1])[:5]:
        print(f"    {byte_seq[:20]}: {prob:.4f}")

    # Sample next bytes
    demo_sampled = demo_adapter.sample_next_bytes(demo_prefix, max_length=10)
    print(f"\nSampled: {demo_sampled}")

    # Example 2: Demonstrate determinism
    print("\n" + "="*50)
    print("Determinism Test\n")

    adapter1 = ByteSamplerAdapter(model_endpoint="test", rng_seed=123)
    adapter2 = ByteSamplerAdapter(model_endpoint="test", rng_seed=123)

    det_prefix = b"cici_cp001"
    sample1 = adapter1.sample_next_bytes(det_prefix)
    sample2 = adapter2.sample_next_bytes(det_prefix)

    print(f"Adapter 1: {sample1}")
    print(f"Adapter 2: {sample2}")
    print(f"Match: {sample1 == sample2}")

    # Example 3: Show Valid Covering Tree
    print("\n" + "="*50)
    print("Valid Covering Tree Example\n")

    vct_prefix = b"ci"
    vct_paths = demo_adapter.marginalize_tokens(vct_prefix)

    print(f"Prefix: {vct_prefix}")
    print(f"Valid token paths: {len(vct_paths)}")
    for idx, path in enumerate(vct_paths[:5]):
        print(f"\nPath {idx+1}:")
        print(f"  Tokens: {path.tokens}")
        print(f"  Bytes: {path.bytes_covered}")
        print(f"  Probability: {path.probability:.6f}")
        print(f"  Overshoot: {path.overshoot_bytes}")


if __name__ == "__main__":
    _demo()
