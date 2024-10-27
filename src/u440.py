import dataclasses
import re
from functools import cached_property

# First attempt at an universal version schema with all the features of PEP 440 combined.
# It only uses 56 out of 64 bits and was going to tweak the dev/pre/post bits until I realized
# these are only combined less than 0.5% of the time.
MASKS_u56 = (
    ("epoch", 0xC, 62),  # 2-bit = 0, 1, 2, 3
    ("v", 0, 0x3FFF, 48),  # 14-bit = 0..16383
    ("v", 1, 0xFF, 40),  # 8-bit = 0..255
    ("v", 2, 0xFF, 32),  # 8-bit = 0..255
    ("v", 3, 0xFF, 24),  # 8-bit = 0..255
    ("post?", 0x1, 22),  # 1-bit = false, true
    ("pre?", 0x3, 20),  # 2-bit = 00 a, 01 b, 10 rc, 11 final
    ("!dev?", 0x1, 23),  # 1-bit = true, false
    ("post", 0xF, 12),  # 4-bit = 0..15
    ("pre", 0xF, 8),  # 4-bit = 0..15
    ("dev", 0xF, 16),  # 4-bit = 0..15
    ("unused", 0xFF, 0),  # 8-bit 0
)

# Mask with only one type of extra version component (e.g. a, b, rc, post, dev, etc.)
# This is based on uv implementation. I use 4 bits for the extra component instead of 3 because
# I like even numbers better :).
# All number portions are 12 bits which is the sweet spot for representing 92.6% of the version numbers found.
MASKS_u64 = (
    ("epoch", 0x0, 64),  # 0-bit = 0
    ("v", 0, 0xFFF, 52),  # 12-bit = 0..4096
    ("v", 1, 0xFFF, 40),  # 12-bit = 0..4096
    ("v", 2, 0xFFF, 28),  # 12-bit = 0..4096
    ("v", 3, 0xFFF, 16),  # 12-bit = 0..4096
    ("dev|pre|post?", 0x7, 12),  # 4-bit = 0..15
    ("dev|pre|post", 0xFFF, 0),  # 12-bit = 0..4096
)

# https://github.com/astral-sh/uv/blob/f23d9c1a/crates/uv-pep440/src/version.rs#L790-L870
# This is a reimplementation of uv's u64 masking which they claim >90% of version numbers covered, but my analysis
# says about 86.8% when filtering distinct version numbers of each PyPI package.
# I guess the last part being so large is to allow for YYYYMM in the dev/pre/post components, except it
# works up until Dec 2097 :) #Y2K98bug
MASKS_uv64 = (
    ("epoch", 0x0, 64),  # 0-bit = 0
    ("v", 0, 0xFFFF, 48),  # 16-bit = 0..65536
    ("v", 1, 0xFF, 40),  # 8-bit = 0..255
    ("v", 2, 0xFF, 32),  # 8-bit = 0..255
    ("v", 3, 0xFF, 24),  # 8-bit = 0..255
    ("dev|pre|post?", 0x7, 21),  # 3-bit = 0..8
    ("dev|pre|post", 0x1FFFFF, 0),  # 21-bit = 0..2097151
)


VERSION_PATTERN = r"""
    v?
    (?:
        (?:(?P<epoch>[0-9]+)!)?                           # epoch
        (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
        (?P<pre>                                          # pre-release
            [-_\.]?
            (?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview))
            [-_\.]?
            (?P<pre_n>[0-9]+)?
        )?
        (?P<post>                                         # post release
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [-_\.]?
                (?P<post_l>post|rev|r)
                [-_\.]?
                (?P<post_n2>[0-9]+)?
            )
        )?
        (?P<dev>                                          # dev release
            [-_\.]?
            (?P<dev_l>dev)
            [-_\.]?
            (?P<dev_n>[0-9]+)?
        )?
    )
    (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?       # local version
"""

spec = re.compile(
    r"^\s*" + VERSION_PATTERN + r"\s*$",
    re.VERBOSE | re.IGNORECASE,
)


pre_types = {
    "a": "a",
    "alpha": "a",
    "b": "b",
    "beta": "b",
    "c": "rc",
    "rc": "rc",
    "pre": "rc",
    "preview": "rc",
    "final": "final",
}

pre_types_int = {"a": 0, "b": 1, "rc": 2, "final": 3}
devprepost_types_int = {
    "min": 0,
    "dev": 1,
    "a": 2,
    "b": 3,
    "rc": 4,
    "final": 5,
    "post": 6,
    "max": 7,
}


@dataclasses.dataclass
class Version:
    epoch: int
    version: list[int]
    release: str
    pre: int | None
    dev: int | None
    post: int | None
    local: str

    mask: tuple = MASKS_u64
    _masks = {
        "u56": MASKS_u56,
        "u64": MASKS_u64,
        "uv64": MASKS_uv64,
    }

    @classmethod
    def load(cls, vtext, raise_error=True, mask="u64"):
        match = spec.match(vtext)
        if not match:
            if raise_error:
                raise ValueError("Invalid version text")
            return None

        return cls(
            epoch=int(match["epoch"] or 0),
            version=[int(x) for x in match["release"].split(".")],
            release=(release := pre_types[(match["pre_l"] or "final").lower()]),
            pre=int(match["pre_n"] or 0) if release != "final" else None,
            dev=int(match["dev_n"] or 0) if match["dev"] else None,
            post=int(match["post_n1"] or match["post_n2"] or 0)
            if match["post"]
            else None,
            local=match["local"],
            mask=cls._masks[mask],
        )

    @cached_property
    def u64(self):
        num = 0
        if len(self.version) > 4:
            return None
        for maskv in self.mask:
            match maskv:
                case ("epoch", mask, shift):
                    val = self.epoch
                case ("v", n, mask, shift):
                    val = self.version[n] if len(self.version) > n else 0
                case ("!dev?", mask, shift):
                    val = self.dev is None
                case ("post?", mask, shift):
                    val = self.post is not None
                case ("pre?", mask, shift):
                    val = pre_types_int[self.release]
                case ("dev", mask, shift):
                    val = self.dev or 0
                case ("post", mask, shift):
                    val = self.post or 0
                case ("pre", mask, shift):
                    val = self.pre or 0
                case ("unused", mask, shift):
                    val = 0
                case ("dev|pre|post?", mask, shift):
                    val = None
                    for k, v in {
                        "dev": self.dev,
                        self.release: self.pre,
                        "post": self.post,
                    }.items():
                        if v is not None:
                            if val is not None:
                                return None
                            val = devprepost_types_int[k]
                    if val is None:
                        val = devprepost_types_int["final"]
                case ("dev|pre|post", mask, shift):
                    val = self.dev or self.pre or self.post or 0
            if val > mask:
                return None
            num += (val & mask) << shift
        return num

    def normal(self):
        epoch = f"{self.epoch}!" if self.epoch else ""
        ver = ".".join(map(str, self.version))
        pre = f"{self.release}{self.pre}" if self.release != "final" else ""
        post = f".post{self.post}" if self.post is not None else ""
        dev = f".dev{self.dev}" if self.dev is not None else ""
        return f"{epoch}{ver}{pre}{post}{dev}"

    def __lt__(self, other):
        return self.u64 < other.u64

    def __eq__(self, other):
        return self.u64 == other.u64

    def __repr__(self):
        return self.normal()


def display_ordered(numbers):
    sorted_numbers = sorted(numbers)
    result = [str(sorted_numbers[0])]

    for prev, curr in zip(sorted_numbers, sorted_numbers[1:]):
        result.append("=" if curr == prev else "<")
        result.append(str(curr))

    return " ".join(result)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("version", nargs="+")
    parser.add_argument("--mask", choices=["u56", "u64", "uv64"], default="u64")
    args = parser.parse_args()
    vs = [Version.load(v, mask=args.mask) for v in args.version]
    vsu = [v.u64 for v in vs]
    width = max(len(v.normal()) for v in vs)
    for v, num in zip(vs, vsu):
        if num is None:
            print(v.normal().ljust(width), "no representation")
        else:
            print(v.normal().ljust(width), format(num, "064b"))

    print(display_ordered(vs))
