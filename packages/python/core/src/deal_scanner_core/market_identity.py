"""Conservative model identities for independent advertised-price research."""

import re


def model_identity(title: str) -> str | None:
    text = title.casefold()
    if re.search(
        r"\b(leerverpackung|verpackung|karton|anleitung|lüfter|kühler|wasserkühler|waterblock|backplate|kabel|zubehör)\b",
        text,
    ):
        return None
    if re.search(r"\b(pc|computer|rechner|bundle|konvolut|paket|set|suche|gesuch)\b|\+|\b[2-9]\s*[x×]\b", text):
        return None
    # Full Icy Dock part numbers, not just 'SSD adapter' or a recognized component.
    if re.search(r"icy\s*dock", text):
        codes = re.findall(r"\bmb\d{3}[a-z0-9]*(?:-[a-z0-9]+)*\b", text)
        if len(set(codes)) == 1:
            return "icy dock " + str(codes[0])
    gpu = re.findall(r"\b(rtx|gtx|rx)[ -]?(\d{4})(?:[ -]?(super|ti|xtx|xt))?\b", text)
    if len(gpu) == 1:
        family, number, variant = gpu[0]
        # Do not turn an uncertain two-suffix product into a base GPU comparison.
        if re.search(r"\bti\s+super\b", text):
            variant = "ti super"
        capacity = re.search(r"\b(\d{1,2})\s*gb\b", text)
        if capacity:
            return " ".join(filter(None, [family, number, variant, capacity[1] + "gb"]))
    return None
