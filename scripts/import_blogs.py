#!/usr/bin/env python3
"""Import the two legacy blogs into Hugo page bundles under content/blog/.

Sources (public, no auth):
  * WordPress "Transcisthor"        (public-api.wordpress.com REST v1.1)
  * Blogspot  "El Canto de Lemuria" (Blogger JSON feed)

Each post becomes ``content/blog/<YYYY-MM-DD>-<slug>/index.html`` with YAML
front matter, a sanitised HTML body and its images downloaded next to it.

The script is idempotent: it removes and regenerates every directory under
content/blog/ whose name starts with ``YYYY-MM-DD-`` and never touches any
other file (e.g. ``_index.md``).

Usage (from the repo root):  python3 -I scripts/import_blogs.py

Standard library only. Downloaded content is treated as untrusted data: it is
parsed and re-serialised through an allow-list, never executed.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = ROOT / "content" / "blog"
BUNDLE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")

WP_API = "https://public-api.wordpress.com/rest/v1.1/sites/transcisthor.wordpress.com/posts/?number=100&page={page}"
BS_FEED = "https://elcantodelemuria.blogspot.com/feeds/posts/default?alt=json&max-results=500&start-index={start}"

ORIGIN_WP = "Transcisthor"
ORIGIN_BS = "El Canto de Lemuria"

USER_AGENT = "Mozilla/5.0 (compatible; luna-blog-import/1.0; +https://github.com/)"
TIMEOUT = 20
RETRIES = 3
MAX_IMAGE_BYTES = 30 * 1024 * 1024

EXCLUDED_TERMS = {"uncategorized", "sin categoría", "sin categoria"}


# --------------------------------------------------------------------------
# Networking
# --------------------------------------------------------------------------

class FetchError(Exception):
    pass


def fetch(url: str, max_bytes: int | None = None) -> tuple[bytes, str]:
    """GET ``url`` with retries; returns (body, content-type)."""
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                ctype = resp.headers.get("Content-Type", "") or ""
                if max_bytes is not None:
                    data = resp.read(max_bytes + 1)
                    if len(data) > max_bytes:
                        raise FetchError(f"too large (> {max_bytes} bytes)")
                else:
                    data = resp.read()
                return data, ctype
        except urllib.error.HTTPError as exc:
            last = exc
            if 400 <= exc.code < 500 and exc.code != 429:
                break  # permanent; don't retry
        except FetchError:
            raise
        except Exception as exc:  # network errors, timeouts
            last = exc
        time.sleep(1.0 * (attempt + 1))
    raise FetchError(str(last))


def fetch_json(url: str):
    data, _ = fetch(url)
    return json.loads(data.decode("utf-8"))


# --------------------------------------------------------------------------
# Minimal DOM
# --------------------------------------------------------------------------

VOID = {"br", "img", "hr", "meta", "link", "input", "param", "embed", "source",
        "wbr", "area", "col", "base", "track", "keygen"}
# start tags that implicitly close an open <p>
CLOSES_P = {"address", "article", "aside", "blockquote", "center", "div", "dl",
            "fieldset", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
            "h6", "header", "hr", "main", "nav", "ol", "p", "pre", "section",
            "table", "ul", "figcaption", "dd", "dt", "li"}
P_SCOPE_STOP = {"table", "td", "th", "caption", "object", "button", "li", "blockquote", "figure"}


class Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: dict | None = None, children: list | None = None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = children if children is not None else []

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<{self.tag} {self.attrs} ({len(self.children)})>"


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    # -- helpers ---------------------------------------------------------
    def _pop_to(self, idx: int):
        del self.stack[idx:]

    def _find_open(self, tag: str, stop: set[str] = frozenset()) -> int:
        for i in range(len(self.stack) - 1, 0, -1):
            t = self.stack[i].tag
            if t == tag:
                return i
            if t in stop:
                return -1
        return -1

    # -- parser callbacks --------------------------------------------------
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in CLOSES_P:
            i = self._find_open("p", P_SCOPE_STOP)
            if i > 0:
                self._pop_to(i)
        if tag == "li":
            i = self._find_open("li", {"ul", "ol"})
            if i > 0:
                self._pop_to(i)
        elif tag in ("td", "th"):
            for t in ("td", "th"):
                i = self._find_open(t, {"tr", "table"})
                if i > 0:
                    self._pop_to(i)
        elif tag == "tr":
            i = self._find_open("tr", {"table"})
            if i > 0:
                self._pop_to(i)
        node = Node(tag, {k.lower(): (v if v is not None else "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in VOID:
            return
        i = self._find_open(tag)
        if i > 0:
            self._pop_to(i)

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)

    # comments, declarations, PIs: dropped
    def handle_comment(self, data):
        pass

    def handle_decl(self, decl):
        pass

    def unknown_decl(self, data):
        pass

    def handle_pi(self, data):
        pass


def parse_html(src: str) -> Node:
    tb = TreeBuilder()
    tb.feed(src)
    tb.close()
    return tb.root


# --------------------------------------------------------------------------
# Cleaning: raw DOM -> normalised DOM (allow-listed tags only)
# --------------------------------------------------------------------------

DROP = {"script", "style", "link", "meta", "noscript", "title", "head", "param",
        "input", "button", "select", "textarea", "option", "svg", "math", "xml",
        "canvas", "audio", "video", "map", "area", "base", "template", "frame",
        "frameset", "applet", "label"}
TRANSPARENT_BLOCK = {"div", "center", "form", "section", "article", "header", "footer",
                     "aside", "main", "nav", "address", "dl", "dt", "dd", "pre",
                     "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption",
                     "fieldset", "legend", "details", "summary", "colgroup", "marquee"}
INLINE_KEEP = {"em", "i", "strong", "b", "a"}
STRUCTURAL = {"blockquote", "ul", "ol", "li", "h2", "h3", "h4", "figure", "figcaption",
              "hr", "embed-wrap"}

WIDGET_CLASSES = ("sharedaddy", "jp-relatedposts", "jetpack-likes-widget", "wpcnt",
                  "wordads", "sd-sharing", "sd-like", "wpl-likebox", "post-likes-widget",
                  "addtoany", "blogger-post-footer", "post-share-buttons")
WIDGET_IDS = ("jp-post-flair", "jp-relatedposts", "like-post-wrapper")

TRACKER_HOSTS = ("stats.wordpress.com", "pixel.wp.com", "pixel.quantserve.com",
                 "quantserve.com", "a.triggit.com", "counters.gigya.com",
                 "reverbnation.com", "feeds.feedburner.com", "blogger.com/tracker",
                 "www.blogger.com/img", "statcounter.com", "google-analytics.com",
                 "doubleclick.net", "sitemeter.com")

EMBED_HOSTS = ("youtube.com", "youtube-nocookie.com", "vimeo.com", "soundcloud.com",
               "spotify.com")

IMAGE_HOSTS = ("blogger.googleusercontent.com", "bp.blogspot.com", "ggpht.com",
               "files.wordpress.com", "wp.com", "photobucket.com", "imageshack")
IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|bmp|avif)$", re.I)


def host_of(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def host_matches(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def absolutize(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def is_tracker(src: str, attrs: dict) -> bool:
    low = src.lower()
    if any(t in low for t in TRACKER_HOSTS):
        return True
    for dim in ("width", "height"):
        v = attrs.get(dim, "").strip().rstrip("px")
        if v.isdigit() and int(v) <= 2:
            return True
    style = attrs.get("style", "").replace(" ", "").lower()
    if "visibility:hidden" in style or "display:none" in style:
        return True
    if re.search(r"(?:^|;)(?:width|height):[0-2]px", style):
        return True
    return False


def youtube_embed(url: str) -> str | None:
    """Return a canonical https YouTube embed URL for any YouTube video URL."""
    url = absolutize(url)
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    vid = None
    if host_matches(host, ("youtube.com", "youtube-nocookie.com")):
        m = re.match(r"^/(?:embed|v)/([A-Za-z0-9_-]{6,})", parts.path)
        if m:
            vid = m.group(1)
        elif parts.path == "/watch":
            vid = urllib.parse.parse_qs(parts.query).get("v", [None])[0]
    elif host == "youtu.be":
        vid = parts.path.strip("/") or None
    if not vid or not re.fullmatch(r"[A-Za-z0-9_-]{6,}", vid):
        return None
    q = urllib.parse.parse_qs(parts.query)
    start = q.get("start", [None])[0] or q.get("t", [None])[0]
    suffix = f"?start={int(start)}" if start and str(start).isdigit() else ""
    return f"https://www.youtube.com/embed/{vid}{suffix}"


def embed_node(src: str, title: str = "") -> Node | None:
    src = absolutize(html.unescape(src))
    host = host_of(src)
    if not host_matches(host, EMBED_HOSTS) and host != "youtu.be":
        return None
    yt = youtube_embed(src)
    if host_matches(host, ("youtube.com", "youtube-nocookie.com")) or host == "youtu.be":
        if not yt:
            return None
        src = yt
    elif src.startswith("http:"):
        src = "https:" + src[5:]
    if not src.startswith("https://"):
        return None
    attrs = {"src": src}
    if title:
        attrs["title"] = title
    return Node("embed-wrap", {}, [Node("iframe", attrs)])


def has_class(node: Node, needle: str) -> bool:
    return needle in node.attrs.get("class", "").split()


def find_all(node: Node, tag: str):
    for c in node.children:
        if isinstance(c, Node):
            if c.tag == tag:
                yield c
            yield from find_all(c, tag)


def is_image_href(href: str) -> bool:
    path = urllib.parse.urlsplit(href).path
    return bool(IMAGE_EXT_RE.search(path)) or host_matches(host_of(href), IMAGE_HOSTS) \
        or "/wp-content/uploads/" in path


def only_images(children: list) -> bool:
    imgs = 0
    for c in children:
        if isinstance(c, str):
            if c.strip():
                return False
        elif c.tag == "img":
            imgs += 1
        elif c.tag == "br":
            continue
        else:
            return False
    return imgs > 0


def clean_children(children: list) -> list:
    out = []
    for c in children:
        out.extend(clean(c))
    return out


def caption_table_to_figure(node: Node) -> list:
    caption_cells = [td for td in find_all(node, "td") if has_class(td, "tr-caption")]
    caption = []
    for td in caption_cells:
        caption.extend(clean_children(td.children))
        td.children = []  # don't duplicate below
    body = clean_children(node.children)
    imgs = []
    other = []

    def collect(nodes):
        for n in nodes:
            if isinstance(n, Node) and n.tag == "img":
                imgs.append(n)
            elif isinstance(n, Node) and n.tag in ("a", "div"):
                collect(n.children)
            else:
                other.append(n)

    collect(body)
    if not imgs:
        return [Node("div", {}, body + caption)]
    fig = Node("figure", {}, list(imgs))
    if caption:
        fig.children.append(Node("figcaption", {}, caption))
    return [fig] + ([Node("div", {}, other)] if any(
        not (isinstance(o, str) and not o.strip()) for o in other) else [])


def clean(node) -> list:
    """Return the cleaned replacement(s) for one raw DOM child."""
    if isinstance(node, str):
        return [node]
    tag = node.tag
    attrs = node.attrs

    if ":" in tag:  # MS Word namespaced junk (o:p, st1:place, v:shape, w:...)
        prefix = tag.split(":", 1)[0]
        return [] if prefix in ("v", "w", "m", "xml") else clean_children(node.children)
    if tag in DROP:
        return []

    cls = attrs.get("class", "").lower()
    ident = attrs.get("id", "").lower()
    if any(w in cls for w in WIDGET_CLASSES) or any(ident.startswith(w) for w in WIDGET_IDS):
        return []

    if tag == "img":
        src = absolutize(attrs.get("src", "") or attrs.get("data-orig-file", ""))
        if not src.startswith(("http://", "https://")) or is_tracker(src, attrs):
            return []
        alt = re.sub(r"\s+", " ", attrs.get("alt", "")).strip()
        return [Node("img", {"src": src, "alt": alt})]

    if tag == "iframe":
        n = embed_node(attrs.get("src", ""), attrs.get("title", ""))
        return [n] if n else []

    if tag in ("object", "embed"):
        candidates = [attrs.get("data", ""), attrs.get("src", "")]
        for p in find_all(node, "param"):
            if p.attrs.get("name", "").lower() in ("movie", "src"):
                candidates.append(p.attrs.get("value", ""))
        for e in find_all(node, "embed"):
            candidates.append(e.attrs.get("src", ""))
        for cand in candidates:
            if cand and youtube_embed(cand):
                n = embed_node(cand)
                if n:
                    return [n]
        return []  # dead flash widgets etc.

    if tag == "table":
        if "tr-caption-container" in cls or any(
                has_class(td, "tr-caption") for td in find_all(node, "td")):
            return caption_table_to_figure(node)
        return [Node("div", {}, clean_children(node.children))]

    if tag == "a":
        href = absolutize(html.unescape(attrs.get("href", "")))
        kids = clean_children(node.children)
        if not any((isinstance(k, str) and k.strip()) or isinstance(k, Node) for k in kids):
            return []
        if not re.match(r"^(https?://|mailto:)", href, re.I):
            return kids
        if any(t in href.lower() for t in TRACKER_HOSTS):
            return kids
        if only_images(kids) and is_image_href(href):
            return kids
        return [Node("a", {"href": href}, kids)]

    if tag in INLINE_KEEP:
        return [Node(tag, {}, clean_children(node.children))]
    if tag == "br":
        return [Node("br")]
    if tag == "hr":
        return [Node("hr")]
    if tag == "p":
        return [Node("p", {}, clean_children(node.children))]
    if tag == "h1":
        return [Node("h2", {}, clean_children(node.children))]
    if tag in ("h2", "h3", "h4"):
        return [Node(tag, {}, clean_children(node.children))]
    if tag in ("h5", "h6"):
        return [Node("p", {}, clean_children(node.children))]
    if tag in ("blockquote", "ul", "ol", "li", "figure", "figcaption"):
        return [Node(tag, {}, clean_children(node.children))]
    if tag in TRANSPARENT_BLOCK:
        return [Node("div", {}, clean_children(node.children))]
    # span, font, u, sup, cite, ... and anything unknown: unwrap (keep text)
    return clean_children(node.children)


# --------------------------------------------------------------------------
# Blockify: normalised DOM -> list of well-formed block nodes
# --------------------------------------------------------------------------
# Inline content is linearised into tokens carrying their inline-ancestor
# stack, so we can re-split it into paragraphs/lines (Blogspot poetry uses
# <br> and <div> per line) and rebuild balanced markup.

WS_RE = re.compile(r"[\s ​‌‍﻿]+")


def linearize(children: list, stack: tuple, out: list, flat: bool = False):
    """Turn a node list into tokens. With ``flat`` structural blocks are
    flattened into paragraph breaks (for headings/captions)."""
    for c in children:
        if isinstance(c, str):
            out.append(("text", c, stack))
            continue
        t = c.tag
        if t == "br":
            out.append(("br", None, stack))
        elif t == "img":
            # images were display:block in both blogs: give each its own block
            out.append(("hard", None, stack))
            out.append(("atom", c, stack))
            out.append(("hard", None, stack))
        elif t in INLINE_KEEP:
            linearize(c.children, stack + (c,), out, flat)
        elif t == "div":
            out.append(("soft", None, stack))
            linearize(c.children, stack, out, flat)
            out.append(("soft", None, stack))
        elif t == "p" or (flat and t in STRUCTURAL):
            if t in ("hr", "embed-wrap"):
                continue
            out.append(("hard", None, stack))
            linearize(c.children, stack, out, flat)
            out.append(("hard", None, stack))
        elif t in STRUCTURAL:
            out.append(("block", c, stack))
        else:
            linearize(c.children, stack, out, flat)


def tokens_to_lines(tokens: list) -> list:
    """Return a list of lines (lists of tokens) and 'PARA' markers.

    Empty lists are blank lines (paragraph separators)."""
    lines: list = []
    line: list = []
    has_content = False
    for kind, val, stack in tokens:
        if kind == "text":
            if WS_RE.sub("", val):
                has_content = True
                line.append((kind, val, stack))
            elif line:
                line.append((kind, val, stack))
        elif kind == "atom":
            has_content = True
            line.append((kind, val, stack))
        elif kind == "br":
            lines.append((line if has_content else [], stack))
            line, has_content = [], False
        elif kind == "soft":
            if has_content:
                lines.append((line, stack))
            line, has_content = [], False
        elif kind == "hard":
            if has_content:
                lines.append((line, stack))
            line, has_content = [], False
            lines.append("PARA")
    if has_content:
        lines.append((line, ()))
    return lines


def lines_to_paragraphs(lines: list) -> list:
    paras: list = []
    cur: list = []
    for item in lines:
        if item == "PARA" or not item[0]:
            if cur:
                paras.append(cur)
            cur = []
        else:
            cur.append(item)
    if cur:
        paras.append(cur)
    return paras


def build_inline(lines: list) -> list:
    """Rebuild balanced inline markup from lines of tokens (joined by <br>)."""
    root = Node("#frag")
    path: list = []  # list of (orig_node, clone)

    def current():
        return path[-1][1] if path else root

    def sync(stack):
        k = 0
        while k < len(path) and k < len(stack) and path[k][0] is stack[k]:
            k += 1
        del path[k:]
        for orig in stack[k:]:
            clone = Node(orig.tag, dict(orig.attrs))
            current().children.append(clone)
            path.append((orig, clone))

    for li, (toks, _end_stack) in enumerate(lines):
        if li:
            # place the <br> in the deepest context shared by both sides
            sync(lines[li - 1][1])
            current().children.append(Node("br"))
        # strip whitespace-only tokens at line edges
        while toks and toks[0][0] == "text" and not WS_RE.sub("", toks[0][1]):
            toks = toks[1:]
        while toks and toks[-1][0] == "text" and not WS_RE.sub("", toks[-1][1]):
            toks = toks[:-1]
        prev_space = True  # at line start, drop leading whitespace
        for idx, (kind, val, stack) in enumerate(toks):
            sync(stack)
            if kind == "text":
                txt = WS_RE.sub(" ", val)
                if prev_space:
                    txt = txt.lstrip(" ")
                if idx == len(toks) - 1:
                    txt = txt.rstrip(" ")
                if txt:
                    current().children.append(txt)
                    prev_space = txt.endswith(" ")
            else:
                current().children.append(val)
                prev_space = False
        # trailing whitespace before a later atom-less end is handled above
    prune_inline(root)
    return root.children


def has_content(node) -> bool:
    if isinstance(node, str):
        return bool(WS_RE.sub("", node))
    if node.tag in ("img", "iframe", "embed-wrap", "hr"):
        return True
    return any(has_content(c) for c in node.children)


def prune_inline(node: Node):
    """Remove inline elements without content (keeping a separating space)."""
    new = []
    for c in node.children:
        if isinstance(c, Node) and c.tag in INLINE_KEEP:
            prune_inline(c)
            if not has_content(c):
                if any(isinstance(x, str) and x for x in c.children):
                    new.append(" ")
                continue
        new.append(c)
    # merge adjacent text / identical inline siblings, collapse double spaces
    merged = []
    for c in new:
        prev = merged[-1] if merged else None
        if isinstance(c, str) and isinstance(prev, str):
            merged[-1] = re.sub(r" {2,}", " ", prev + c)
        elif (isinstance(c, Node) and isinstance(prev, Node) and c.tag == prev.tag
              and c.tag in INLINE_KEEP and c.attrs == prev.attrs):
            prev.children.extend(c.children)
            prune_inline(prev)
        else:
            merged.append(c)
    node.children = merged


def inline_content(children: list) -> list:
    """Flatten children to inline content (paragraph breaks become <br>)."""
    toks: list = []
    linearize(children, (), toks, flat=True)
    paras = lines_to_paragraphs(tokens_to_lines(toks))
    lines = [ln for p in paras for ln in p]
    return build_inline(lines) if lines else []


def blockify(children: list) -> list:
    toks: list = []
    linearize(children, (), toks)
    blocks: list = []
    seg: list = []

    def flush():
        if not seg:
            return
        for para in lines_to_paragraphs(tokens_to_lines(seg)):
            inline = build_inline(para)
            if not any(has_content(x) for x in inline):
                continue
            real = [x for x in inline if not (isinstance(x, str) and not x.strip())]
            if real and all(isinstance(x, Node) and x.tag == "img" for x in real):
                blocks.append(Node("figure", {}, real))  # standalone image
            else:
                blocks.append(Node("p", {}, inline))
        seg.clear()

    for tok in toks:
        if tok[0] == "block":
            flush()
            blocks.extend(process_block(tok[1]))
        else:
            seg.append(tok)
    flush()
    return blocks


def process_block(node: Node) -> list:
    t = node.tag
    if t == "hr":
        return [Node("hr")]
    if t == "embed-wrap":
        return [node]
    if t in ("h2", "h3", "h4"):
        inl = inline_content(node.children)
        return [Node(t, {}, inl)] if any(has_content(x) for x in inl) else []
    if t == "blockquote":
        inner = blockify(node.children)
        return [Node("blockquote", {}, inner)] if inner else []
    if t in ("ul", "ol"):
        items: list = []
        loose: list = []

        def flush_loose():
            if loose:
                content = blockify(list(loose))
                if content:
                    if items:
                        items[-1].children.extend(content)
                    else:
                        items.append(Node("li", {}, content))
                loose.clear()

        for c in node.children:
            if isinstance(c, Node) and c.tag == "li":
                flush_loose()
                content = blockify(c.children)
                if not content:
                    continue
                if len(content) == 1 and content[0].tag == "p":
                    content = content[0].children
                items.append(Node("li", {}, content))
            else:
                loose.append(c)
        flush_loose()
        return [Node(t, {}, items)] if items else []
    if t == "li":  # stray li outside a list
        return blockify(node.children)
    if t == "figure":
        imgs, embeds, caption_nodes = [], [], []

        def collect(nodes):
            for n in nodes:
                if not isinstance(n, Node):
                    continue
                if n.tag == "img":
                    imgs.append(n)
                elif n.tag == "embed-wrap":
                    embeds.append(n)
                elif n.tag == "figcaption":
                    caption_nodes.extend(n.children)
                else:
                    collect(n.children)

        collect(node.children)
        cap = inline_content(caption_nodes) if caption_nodes else []
        cap_ok = any(has_content(x) for x in cap)
        out: list = list(embeds)
        if imgs:
            fig = Node("figure", {}, list(imgs))
            if cap_ok:
                fig.children.append(Node("figcaption", {}, cap))
            out.insert(0, fig)
        elif cap_ok:
            out.append(Node("p", {}, [Node("em", {}, cap)]))
        return out
    if t == "figcaption":  # stray figcaption
        return blockify(node.children)
    return blockify(node.children)


# --------------------------------------------------------------------------
# Serialisation and text helpers
# --------------------------------------------------------------------------

def esc_text(s: str) -> str:
    return html.escape(s, quote=False)


def esc_attr(s: str) -> str:
    return html.escape(s, quote=True)


def ser_inline(nodes: list) -> str:
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append(esc_text(n))
        elif n.tag == "br":
            out.append("<br>\n")
        elif n.tag == "img":
            out.append(f'<img src="{esc_attr(n.attrs["src"])}" alt="{esc_attr(n.attrs.get("alt", ""))}">')
        elif n.tag == "a":
            href = n.attrs.get("href", "")
            extra = ' rel="noopener" target="_blank"' if href.lower().startswith("http") else ""
            out.append(f'<a href="{esc_attr(href)}"{extra}>{ser_inline(n.children)}</a>')
        else:
            out.append(f"<{n.tag}>{ser_inline(n.children)}</{n.tag}>")
    return "".join(out)


def ser_blocks(blocks: list, indent: str = "") -> str:
    out = []
    for b in blocks:
        t = b.tag
        if t == "hr":
            out.append(f"{indent}<hr>")
        elif t == "embed-wrap":
            ifr = b.children[0]
            title = ifr.attrs.get("title")
            title_attr = f' title="{esc_attr(title)}"' if title else ""
            out.append(f'{indent}<div class="embed"><iframe src="{esc_attr(ifr.attrs["src"])}"'
                       f'{title_attr} loading="lazy" allowfullscreen></iframe></div>')
        elif t == "figure":
            parts = [ser_inline([c]) for c in b.children if c.tag == "img"]
            cap = [c for c in b.children if c.tag == "figcaption"]
            if cap:
                parts.append(f"<figcaption>{ser_inline(cap[0].children)}</figcaption>")
            out.append(f"{indent}<figure>" + "".join(parts) + "</figure>")
        elif t in ("ul", "ol", "blockquote"):
            inner = []
            if t == "blockquote":
                inner.append(ser_blocks(b.children, indent + "  "))
            else:
                for li in b.children:
                    if li.children and all(isinstance(c, Node) and c.tag in
                                           ("p", "ul", "ol", "blockquote", "figure", "hr",
                                            "embed-wrap", "h2", "h3", "h4")
                                           for c in li.children):
                        inner.append(f"{indent}  <li>\n{ser_blocks(li.children, indent + '    ')}\n{indent}  </li>")
                    elif any(isinstance(c, Node) and c.tag in ("p", "ul", "ol", "blockquote")
                             for c in li.children):
                        # mixed inline + block: wrap inline runs in <p>
                        fixed, run = [], []
                        for c in li.children:
                            if isinstance(c, Node) and c.tag in ("p", "ul", "ol", "blockquote", "figure", "hr", "embed-wrap"):
                                if run:
                                    fixed.append(Node("p", {}, run))
                                    run = []
                                fixed.append(c)
                            else:
                                run.append(c)
                        if run:
                            fixed.append(Node("p", {}, run))
                        inner.append(f"{indent}  <li>\n{ser_blocks(fixed, indent + '    ')}\n{indent}  </li>")
                    else:
                        inner.append(f"{indent}  <li>{ser_inline(li.children)}</li>")
            out.append(f"{indent}<{t}>\n" + "\n".join(inner) + f"\n{indent}</{t}>")
        else:  # p, h2-h4
            out.append(f"{indent}<{t}>{ser_inline(b.children)}</{t}>")
    return "\n".join(out)


def plain_text(nodes: list, br: str = " ") -> str:
    parts = []
    for n in nodes:
        if isinstance(n, str):
            parts.append(n)
        elif n.tag == "br":
            parts.append(br)
        elif n.tag in ("p", "h2", "h3", "h4", "li", "figcaption", "blockquote", "ul", "ol"):
            parts.append(" " + plain_text(n.children, br) + " ")
        elif n.tag in ("img", "embed-wrap", "hr"):
            parts.append(" ")
        else:
            parts.append(plain_text(n.children, br))
    return "".join(parts)


def squash(s: str) -> str:
    return WS_RE.sub(" ", s).strip()


def truncate_words(s: str, limit: int) -> str:
    s = squash(s)
    if len(s) <= limit:
        return s
    cut = s[:limit + 1]
    sp = cut.rfind(" ")
    cut = cut[:sp] if sp > limit * 0.5 else s[:limit]
    return cut.rstrip(" ,;:.-–—…(«\"'") + "…"


def text_lines(blocks: list) -> list[str]:
    lines = []
    for b in blocks:
        if b.tag not in ("p", "h2", "h3", "h4", "blockquote", "ul", "ol"):
            continue
        for line in plain_text([b], br="\n").split("\n"):
            line = squash(line)
            if line:
                lines.append(line)
    return lines


def title_from_text(blocks: list) -> str:
    """Title for an untitled post: its first non-empty line (a very short
    first line such as "Parte 1:" is joined with the next one)."""
    lines = text_lines(blocks)
    if not lines:
        return ""
    line = lines[0]
    if len(line) < 15 and len(lines) > 1:
        line = f"{line} {lines[1]}"
    if len(line) <= 60:
        return line.rstrip(" ,;:-–—")
    return truncate_words(line, 60)


def slugify(s: str, maxlen: int = 60) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > maxlen:
        cut = s[:maxlen + 1]
        i = cut.rfind("-")
        s = cut[:i] if i > maxlen * 0.5 else s[:maxlen]
        s = s.strip("-")
    return s or "entrada"


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------

def sniff_ext(data: bytes, ctype: str) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:12] in (b"ftypavif", b"ftypavis"):
        return "avif"
    if data.startswith(b"BM") and "bmp" in ctype:
        return "bmp"
    return None  # svg/html/unknown are rejected (untrusted; never served as-is)


def upgrade_image_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if host_matches(host, ("blogger.googleusercontent.com", "bp.blogspot.com", "ggpht.com")):
        path = parts.path
        segs = path.split("/")
        if len(segs) >= 3 and re.fullmatch(r"[swh]\d+(-[a-z0-9-]*)?|w\d+-h\d+(-[a-z0-9-]*)?", segs[-2]):
            segs[-2] = "s1600"
            path = "/".join(segs)
        path = re.sub(r"=[swh]\d+[^/]*$", "=s1600", path)
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))
    if host.endswith("files.wordpress.com") or "/wp-content/uploads/" in parts.path \
            or host_matches(host, ("wp.com",)):
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return url


def candidate_urls(url: str) -> list[str]:
    cands = []
    for u in (upgrade_image_url(url), url):
        if u.startswith("http://"):
            cands.append("https://" + u[7:])
        cands.append(u)
    seen, out = set(), []
    for u in cands:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


class ImageStats:
    def __init__(self):
        self.ok = 0
        self.failed: list[tuple[str, str, str]] = []  # (bundle, url, reason)
        self.bytes = 0


def download_image(url: str) -> tuple[bytes, str] | tuple[None, str]:
    reason = "no candidates"
    for cand in candidate_urls(url):
        try:
            data, ctype = fetch(cand, MAX_IMAGE_BYTES)
        except FetchError as exc:
            reason = f"{cand}: {exc}"
            continue
        ext = sniff_ext(data, ctype.lower())
        if ext:
            return data, ext
        reason = f"{cand}: not a raster image ({ctype or 'unknown type'})"
    return None, reason


def image_key(url: str) -> str:
    """Identity used to dedupe images (same file at different sizes)."""
    up = upgrade_image_url(absolutize(url))
    parts = urllib.parse.urlsplit(up)
    return (parts.hostname or "") + parts.path


def basename_key(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    name = path.rsplit("/", 1)[-1].lower()
    return re.sub(r"-\d+x\d+(?=\.\w+$)", "", name)


# --------------------------------------------------------------------------
# Post assembly
# --------------------------------------------------------------------------

def iter_imgs(blocks: list):
    for b in blocks:
        if isinstance(b, Node):
            if b.tag == "img":
                yield b
            else:
                yield from iter_imgs(b.children)


def alt_is_filename(alt: str, src: str) -> bool:
    """True for alts that are just the image file name (e.g. "Bastion-600x300")."""
    def norm(x):
        return re.sub(r"[^a-z0-9]", "", x.lower())
    stem = urllib.parse.unquote(urllib.parse.urlsplit(src).path.rsplit("/", 1)[-1])
    stem = re.sub(r"\.\w+$", "", stem)
    a = re.sub(r"\.\w{3,4}$", "", alt.strip())
    return bool(a) and (norm(a) == norm(stem) or (" " not in a and re.search(r"[-_]\d|\d+x\d+|^img|^dsc|^image", a.lower()) is not None))


def yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def normalize_date(s: str) -> str:
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$", s.strip())
    if not m:
        raise ValueError(f"unexpected date format: {s!r}")
    return m.group(1) + m.group(2)


def clean_title(raw: str) -> str:
    return squash(html.unescape(raw or ""))


def build_body(raw_html: str) -> list:
    dom = parse_html(raw_html or "")
    cleaned = clean_children(dom.children)
    return blockify(cleaned)


def collect_wp() -> list[dict]:
    posts, page, found = [], 1, None
    while True:
        data = fetch_json(WP_API.format(page=page))
        found = data.get("found", 0)
        batch = data.get("posts", [])
        posts.extend(batch)
        if not batch or len(posts) >= found:
            break
        page += 1
    out = []
    for p in posts:
        terms = []
        for group in (p.get("categories") or {}, p.get("tags") or {}):
            for name in group:  # dict keyed by display name
                terms.append(squash(html.unescape(name)))
        out.append({
            "origin": ORIGIN_WP,
            "title": clean_title(p.get("title", "")),
            "date": normalize_date(p["date"]),
            "url": p.get("URL", ""),
            "html": p.get("content", ""),
            "terms": terms,
            "featured": absolutize(p.get("featured_image") or ""),
        })
    print(f"WordPress: found={found} fetched={len(out)}")
    return out


def collect_bs() -> list[dict]:
    entries, start, total = [], 1, None
    while True:
        data = fetch_json(BS_FEED.format(start=start))
        feed = data.get("feed", {})
        total = int(feed.get("openSearch$totalResults", {}).get("$t", "0"))
        batch = feed.get("entry", []) or []
        entries.extend(batch)
        if not batch or len(entries) >= total:
            break
        start = len(entries) + 1
    out = []
    for e in entries:
        alt = next((l.get("href", "") for l in e.get("link", []) if l.get("rel") == "alternate"), "")
        if alt.startswith("http://"):
            alt = "https://" + alt[7:]
        content = (e.get("content") or e.get("summary") or {}).get("$t", "")
        out.append({
            "origin": ORIGIN_BS,
            "title": clean_title(e.get("title", {}).get("$t", "")),
            "date": normalize_date(e["published"]["$t"]),
            "url": alt,
            "html": content,
            "terms": [squash(c.get("term", "")) for c in e.get("category", []) or []],
            "featured": "",
        })
    print(f"Blogspot: total={total} fetched={len(out)}")
    return out


def dedupe_terms(terms: list[str]) -> list[str]:
    seen, out = set(), []
    for t in terms:
        k = t.casefold()
        if not t or k in EXCLUDED_TERMS or k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def main() -> int:
    if not (ROOT / "content").is_dir():
        print(f"error: {ROOT / 'content'} not found; run from the Hugo repo", file=sys.stderr)
        return 1

    # 1. Fetch everything first so a network failure never leaves us half-written.
    posts = collect_wp() + collect_bs()
    posts.sort(key=lambda p: (p["date"], p["origin"], p["url"]))

    # 2. Remove previously generated bundles (only YYYY-MM-DD-* dirs).
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    for child in sorted(BLOG_DIR.iterdir()):
        if child.is_dir() and BUNDLE_RE.match(child.name):
            shutil.rmtree(child)

    stats = ImageStats()
    used_slugs: dict[str, int] = {}
    report = {"untitled": [], "odd": [], "count": {ORIGIN_WP: 0, ORIGIN_BS: 0}}

    for post in posts:
        blocks = build_body(post["html"])
        title = post["title"]
        if not title:
            title = title_from_text(blocks) or "Sin título"
            report["untitled"].append((post["date"][:10], title, post["url"]))

        base = slugify(title.rstrip("…"))
        n = used_slugs.get(base, 0) + 1
        used_slugs[base] = n
        slug = base if n == 1 else f"{base}-{n}"
        bundle = BLOG_DIR / f"{post['date'][:10]}-{slug}"
        bundle.mkdir(parents=True)

        # Images in the body
        local_by_key: dict[str, str] = {}
        counter = 0
        for img in iter_imgs(blocks):
            src = img.attrs["src"]
            key = image_key(src)
            if key in local_by_key:
                img.attrs["src"] = local_by_key[key]
            else:
                data, ext_or_reason = download_image(src)
                if data is None:
                    stats.failed.append((bundle.name, src, ext_or_reason))
                    local_by_key[key] = src
                else:
                    counter += 1
                    name = f"img-{counter:02d}.{ext_or_reason}"
                    (bundle / name).write_bytes(data)
                    stats.ok += 1
                    stats.bytes += len(data)
                    local_by_key[key] = name
                    img.attrs["src"] = name
            if not img.attrs.get("alt") or alt_is_filename(img.attrs["alt"], src):
                img.attrs["alt"] = title

        # WordPress featured image -> front matter (only if not already in body)
        image_fm = None
        if post["featured"]:
            body_names = {basename_key(u) for u in local_by_key}
            if basename_key(post["featured"]) not in body_names:
                data, ext_or_reason = download_image(post["featured"])
                if data is None:
                    stats.failed.append((bundle.name, post["featured"], ext_or_reason))
                else:
                    image_fm = f"featured.{ext_or_reason}"
                    (bundle / image_fm).write_bytes(data)
                    stats.ok += 1
                    stats.bytes += len(data)

        if not blocks:
            # Only a dead widget (e.g. Flash music player) was in the post.
            blocks = [Node("p", {}, [Node("em", {}, [
                "Esta entrada contenía un reproductor multimedia antiguo que ya no está disponible."])])]
            report["odd"].append((bundle.name, "body was only a dead widget; placeholder note inserted"))
        body_html = ser_blocks(blocks)
        text = squash(plain_text(blocks))
        summary = truncate_words(text, 200) if text else ""
        tags = dedupe_terms(post["terms"])

        kinds = {b.tag for b in blocks}
        if not text:
            report["odd"].append((bundle.name, "no text; blocks=" + ",".join(sorted(kinds)) if kinds else "empty body"))
        elif len(text) < 80:
            report["odd"].append((bundle.name, f"very short text ({len(text)} chars); blocks=" + ",".join(sorted(kinds))))
        elif "embed-wrap" in kinds and len(text) < 200:
            report["odd"].append((bundle.name, "mostly an embed"))

        fm = ["---",
              f"title: {yaml_str(title)}",
              f"date: {post['date']}",
              f"origen: [{yaml_str(post['origin'])}]",
              f"original_url: {yaml_str(post['url'])}"]
        if tags:
            fm.append("tags: [" + ", ".join(yaml_str(t) for t in tags) + "]")
        if image_fm:
            fm.append(f"image: {yaml_str(image_fm)}")
        if summary:
            fm.append(f"summary: {yaml_str(summary)}")
        fm.append("---")
        (bundle / "index.html").write_text("\n".join(fm) + "\n" + body_html + "\n", encoding="utf-8")
        report["count"][post["origin"]] += 1

    # 3. Report
    print(f"\nBundles written: {sum(report['count'].values())} {report['count']}")
    print(f"Images downloaded: {stats.ok} ({stats.bytes / 1024 / 1024:.1f} MiB), failed: {len(stats.failed)}")
    for b, url, reason in stats.failed:
        print(f"  FAIL {b}: {url}\n       {reason}")
    if report["untitled"]:
        print("Untitled posts (generated titles):")
        for d, t, u in report["untitled"]:
            print(f"  {d}  {t}  <{u}>")
    if report["odd"]:
        print("Posts worth a look:")
        for b, why in report["odd"]:
            print(f"  {b}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
