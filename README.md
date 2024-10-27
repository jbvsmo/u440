u440 - Python Versioning Schema
----

This project is a playground for PEP 440 versioning representations.
This is inspired by the awesome job [uv](https://astral.sh/uv) team did to implement PEP 440 in Rust where most
versions can be represented and thus compared with each other using only a single 64-bit unsigned integer (u64).

To run this project:
```python
uv run src/u440.py 1.0 1.0a 1.0rc 1.0.0pre 1.0.0.0post0 1.0post1 1.0dev
1.0           0000000000010000000000000000000000000000000000000101000000000000
1.0a0         0000000000010000000000000000000000000000000000000010000000000000
1.0rc0        0000000000010000000000000000000000000000000000000100000000000000
1.0.0rc0      0000000000010000000000000000000000000000000000000100000000000000
1.0.0.0.post0 0000000000010000000000000000000000000000000000000110000000000000
1.0.post1     0000000000010000000000000000000000000000000000000110000000000001
1.0.dev0      0000000000010000000000000000000000000000000000000001000000000000
1.0.dev0 < 1.0a0 < 1.0rc0 = 1.0.0rc0 < 1.0 < 1.0.0.0.post0 < 1.0.post1
```

There are two `--mask` available: u64 (our default) and uv64 which is implemented from
the [uv spec](https://github.com/astral-sh/uv/blob/f23d9c1a/crates/uv-pep440/src/version.rs#L790-L870). 


Based on my tests, for 6.6 million version identifiers extracted from PyPI, the original:
```
Can fit uv u64 representation:
yes: 5750855 (86.82%)
 no: 872885 (13.18%)
```

This project presents a bit mask capable of representing even more of the version numbers found.
```
Can fit our u64 representation:
yes: 6130619 (92.56%)
 no: 493121 (7.44%)
```

Bit usage for our u64 representation:

| Field 	| v0 	| v1 	| v2 	| v3 	| release 	| num 	|
|---	|---	|---	|---	|---	|---	|---	|
|  	| ............ 	| ............ 	| ............ 	| ............ 	| .... 	| ............ 	|
| Bits 	| 12 	| 12 	| 12 	| 12 	| 4 	| 12 	|
| Mask 	| 0xFFF << 52 	| 0xFFF << 40 	| 0xFFF << 28 	| 0xFFF << 16 	| 0x7 << 12 	| 0xFFF << 0 	|

The v0..v3 fields are the first 4 segments of the version number. The release field is
the pre/post/dev/final component. The num field is the number of the release version.

**Important:** This does not mean it will be better than uv's implementation or that it
will indeed cover a greater percentage of the version number comparisons as obscure
and old PyPI packages might never be used and e.g. NumPy will have its versions
compared millions of times more often, and they have well-behaved version numbers.


---

Validation:
----

I believe the numbers found here diverge from the ones found in uv's implementation since I used filtered
unique version numbers from each package, resulting in a 6.6M registers as oposed to the 11M used by uv.
We don't know their methodology, but it is possible our datasets are not the same. They do claim to use
Google BigQuery, which is what I also used.

From [Google BigQuery](https://cloud.google.com/bigquery) I fetched the distinct data of each project
and saved it as JSONL file which I provided zipped in this project for reproducibility.

Here is the query used:
```sql
SELECT DISTINCT name, version
FROM `bigquery-public-data.pypi.distribution_metadata`
ORDER BY version
```

Notice several version numbers, specially ones in the beginning of the file, are invalid.
I assume the [regex supplied](https://packaging.python.org/en/latest/specifications/version-specifiers/#appendix-parsing-version-strings-with-regular-expressions) by Python packaging docs is the de facto standard
and I will only care about version numbers it matches. Only 0.06% failed to parse.

Below are part of the statistics. You can `uv run src/validation.py` to see the full output.

```
       total: 6623740 (100.00%)  All version numbers exported from PyPI
       valid: 6619525 (99.94%)   All the ones parsed via PyPI's regex
      failed: 4215 (0.06%)       The amount failed to parse
       local: 1 (0.00%)          Versions using +local suffix
         pre: 402436 (6.08%)     Versions with pre-release component (a, b, rc, etc.)
        post: 80329 (1.21%)      Versions with post-release component (post)
         dev: 397048 (5.99%)     Versions with development component (dev)
    pre+post: 2991 (0.05%)       Versions with pre and post components
     pre+dev: 15635 (0.24%)      Versions with pre and dev components
    dev+post: 11564 (0.17%)      Versions with dev and post components
pre+post+dev: 357 (0.01%)        Versions with pre, post and dev components
       epoch: 581 (0.01%)        Versions with epoch component

segments:                        Number of segments in each version
  3: 5630334 (85.00%)
  2: 485216 (7.33%)
  4: 300946 (4.54%)
  6: 92796 (1.40%)
  5: 76872 (1.16%)
  1: 31090 (0.47%)
...: 2271 (0.03%)

```

Notes:

 - Most versions have 4 or fewer segments.
 - There are more releases with 6 segments than with 5 segments. But only an additional >1% of usage on each.
 - The epoch component since is almost always 0.
 - The dev/pre/post components are only combined less than 0.5% of the time.
 - The 1st segment fits a number of
   - 16-bit: 6595912 (99.58%)
   - 14-bit: 6595641 (99.58%)
   - 12-bit: 6592893 (99.53%)
   - 10-bit: 6488997 (97.97%)
   - 8-bit: 6488026 (97.95%)
 - The remaining segments (all compared at once) fit a number of
   - 16-bit: 6549014 (98.87%)
   - 14-bit: 6543151 (98.78%)
   - 12-bit: 6530678 (98.60%)
   - 10-bit: 6434829 (97.15%)
   - 8-bit: 6182772 (93.34%)

So my conclusion is that using 12 bits for every segment is a good trade-off for supporting 4 segments and a 
pre/post/dev component. There is a big drop when using 8 bits for most segments and most if not all of my
optimization are based solely on this fact (about 5%). Also, there is no gain in using 16-bit numbers for the
first segment as uv does.