"""
Yes, I know these would be better with a dataframe or queried with something cool like DuckDB.
I wanted to keep it simple and did this in a half an hour.
"""

import collections
import json
import pathlib
import pickle
import zipfile

from old import Version


def load_version_data():
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    pk_file_path = root / "versions.pickle"
    zip_file_path = root / "versions.zip"
    if pk_file_path.is_file():
        with pk_file_path.open("rb") as pk_file:
            return pickle.load(pk_file)

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        json_filename = zip_ref.namelist()[0]
        with zip_ref.open(json_filename) as json_file:
            data = [json.loads(line) for line in json_file if line.strip()]

        parse(data)

        with pk_file_path.open("wb") as pk_file:
            pickle.dump(data, pk_file)

    return data


def chunked_list(lst, size):
    """Yield successive chunks from a list, each of the specified size."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def parse(versions):
    for vdata in versions:
        try:
            v = Version.load(vdata["version"])
        except ValueError:
            v = None
        vdata["parsed"] = v
        # vdata["u64"] = v.u64 if v else None
    return versions


def display(
    data: dict[str:int] | list[tuple[str, int]], total: int, sort=True, top=None
):
    if isinstance(data, collections.Counter):
        data = data.most_common()
    else:
        data = data.items()
        if sort:
            data = sorted(data)
    if top and len(data) > top:
        data, extra = data[:top], data[top:]
        data.append(("...", sum(v for k, v in extra)))
    width = max(len(str(k)) for k, v in data)
    out = []
    for k, v in data:
        out.append(f"{k:>{width}}: {v} ({v/total:0.2%})")
    print("\n".join(out))
    print()


print("loading versions...")
all_version_data = load_version_data()
total = len(all_version_data)
versions = [v["parsed"] for v in all_version_data if v["parsed"] is not None]

display(
    {
        "total": total,
        "valid": len(versions),
        "failed": total - len(versions),
        "local": sum(v.local is not None for v in versions),
        "pre": sum(v.release != "final" for v in versions),
        "post": sum(v.post is not None for v in versions),
        "dev": sum(v.dev is not None for v in versions),
        "pre+post": sum(v.release != "final" and v.post is not None for v in versions),
        "pre+dev": sum(v.release != "final" and v.dev is not None for v in versions),
        "dev+post": sum(v.dev is not None and v.post is not None for v in versions),
        "pre+post+dev": sum(
            v.release != "final" and v.post is not None and v.dev is not None
            for v in versions
        ),
        "epoch": sum(v.epoch > 0 for v in versions),
    },
    total,
    sort=False,
)


def bits(n):
    return n.bit_length() or 1


def count(iterable):
    return collections.Counter(iterable)


def count_bits(iterable):
    return collections.Counter(bits(n) for n in iterable)


segments = collections.Counter(len(v.version) for v in versions)
print("segments:")
display(segments, total, top=10)

epoch = count(v.epoch.bit_length() for v in versions)  # epoch may be 0 bits
print("epoch (bits):")
display(epoch, total, top=3)

pre_num = count_bits(v.pre for v in versions if v.release != "final")
print("pre (bits):")
display(pre_num, total, top=10)

post_num = count_bits(v.post for v in versions if v.post is not None)
print("post (bits):")
display(post_num, total, top=10)

dev_num = count_bits(v.dev for v in versions if v.dev is not None)
print("dev (bits):")
display(dev_num, total, top=10)

seg_1st = count_bits(v.version[0] for v in versions)
print("bits for 1st segment:")
display(seg_1st, total, top=10)

seg_2nd = count_bits(v.version[1] for v in versions if len(v.version) > 1)
print("bits for 2nd segment:")
display(seg_2nd, total, top=10)

seg_3rd = count_bits(v.version[2] for v in versions if len(v.version) > 2)
print("bits for 3rd segment:")
display(seg_3rd, total, top=10)

seg_rest = count_bits(max(v.version[1:] or [0]) for v in versions)
print("max bits for 2nd to nth segments:")
display(seg_rest, total, top=10)

fit16bit = sum(bits(v.version[0]) <= 16 for v in versions)
print("Can fit 16-bit for 1st segment:")
display({"yes": fit16bit, "no": total - fit16bit}, total, sort=False)

fit14bit = sum(bits(v.version[0]) <= 14 for v in versions)
print("Can fit 14-bit for 1st segment:")
display({"yes": fit14bit, "no": total - fit14bit}, total, sort=False)

fit12bit = sum(bits(v.version[0]) <= 12 for v in versions)
print("Can fit 12-bit for 1st segment:")
display({"yes": fit12bit, "no": total - fit12bit}, total, sort=False)

fit10bit = sum(bits(v.version[0]) <= 10 for v in versions)
print("Can fit 10-bit for 1st segment:")
display({"yes": fit10bit, "no": total - fit10bit}, total, sort=False)

fit8bit = sum(bits(v.version[0]) <= 8 for v in versions)
print("Can fit 8-bit for 1st segment:")
display({"yes": fit8bit, "no": total - fit8bit}, total, sort=False)

fit16bit = sum(bits(max(v.version[1:] or [0])) <= 16 for v in versions)
print("Can fit 16-bit for 2nd to nth segments:")
display({"yes": fit16bit, "no": total - fit16bit}, total, sort=False)

fit14bit = sum(bits(max(v.version[1:] or [0])) <= 14 for v in versions)
print("Can fit 14-bit for 2nd to nth segments:")
display({"yes": fit14bit, "no": total - fit14bit}, total, sort=False)

fit12bit2 = sum(bits(max(v.version[1:] or [0])) <= 12 for v in versions)
print("Can fit 12-bit for 2nd to nth segments:")
display({"yes": fit12bit2, "no": total - fit12bit2}, total, sort=False)

fit10bit = sum(bits(max(v.version[1:] or [0])) <= 10 for v in versions)
print("Can fit 10-bit for 2nd to nth segments:")
display({"yes": fit10bit, "no": total - fit10bit}, total, sort=False)

fit8bit = sum(bits(max(v.version[1:] or [0])) <= 8 for v in versions)
print("Can fit 8-bit for 2nd to nth segments:")
display({"yes": fit8bit, "no": total - fit8bit}, total, sort=False)

fit_uv_repr = sum(
    v.epoch <= 1
    and v.version[0].bit_length() <= 16
    and len(v.version) <= 4
    and bits(max(v.version[1:] or [0])) <= 8
    and ((v.release != "final") + (v.post is not None) + (v.dev is not None)) <= 1
    and bits((v.pre or 0) + (v.post or 0) + (v.dev or 0)) <= 8
    for v in versions
)
print("Can fit uv u64 representation:")
display({"yes": fit_uv_repr, "no": total - fit_uv_repr}, total, sort=False)

fit_v2_repr = sum(
    v.epoch <= 0
    and len(v.version) <= 4
    and bits(max(v.version)) <= 12
    and ((v.release != "final") + (v.post is not None) + (v.dev is not None)) <= 1
    and bits((v.pre or 0) + (v.post or 0) + (v.dev or 0)) <= 21
    for v in versions
)
print("Can fit our u64 representation:")
display({"yes": fit_v2_repr, "no": total - fit_v2_repr}, total, sort=False)
