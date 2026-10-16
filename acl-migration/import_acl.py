"""One-off import of the legacy ACL Cosmetics shop into new-commerce-api via the admin /v1 API.

  python3 -I import_acl.py --backup ~/Downloads/acl-cosm-backup --dry-run
  ACL_EMAIL=... ACL_PASSWORD=... python3 -I import_acl.py --backup ... --api https://api.<domain>/v1

Resumable: progress goes to state.json (next to this file, or --state); a re-run skips what is done.
Stdlib only, Python 3.9+.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

PRICE = 100  # minor units: Rp 1. Real prices are set in admin afterwards.
UNESCAPE = {"0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a"}
TOKEN = re.compile(r"'((?:[^'\\]|\\.)*)'|(NULL)|(-?\d+(?:\.\d+)?)|(\()|(\))|,", re.S)
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# --- legacy dump -------------------------------------------------------------------------------

def unescape(s):
    return re.sub(r"\\(.)", lambda m: UNESCAPE.get(m.group(1), m.group(1)), s, flags=re.S)


def table(dump, name, cols):
    """Rows of `name` as dicts, soft-deleted ones dropped."""
    line = next(l for l in dump.splitlines() if l.startswith("INSERT INTO `%s` VALUES " % name))
    rows, cur = [], None
    for m in TOKEN.finditer(line.split(" VALUES ", 1)[1]):
        if m.group(4):
            cur = []
        elif m.group(5):
            rows.append(dict(zip(cols, cur)))
            cur = None
        elif cur is not None and m.group(0) != ",":
            cur.append(None if m.group(2) else m.group(3) if m.group(3) else unescape(m.group(1)))
    return [r for r in rows if r.get("deleted_at") is None]


def weight_grams(size):
    # ponytail: ml~g heuristic, unknown -> 100 g; real shipping weights get edited in admin.
    m = re.match(r"\s*([\d.,]+)\s*(kg|l|lt|liter|gr|g|gram|ml|)\b", (size or "").lower())
    if not m:
        return 100
    n = float(m.group(1).replace(",", "."))
    return max(1, round(n * 1000 if m.group(2) in ("kg", "l", "lt", "liter") else n))


def load(backup):
    dump = open(os.path.join(backup, "acl_cosm_16102026.sql"), encoding="utf-8", errors="replace").read()
    brands = table(dump, "brands", ["id", "name", "slug", "created_at", "updated_at", "deleted_at"])
    cats = table(dump, "categories", ["id", "name", "slug", "parent_id", "created_at", "updated_at", "deleted_at"])
    products = table(dump, "products", ["id", "name", "slug", "brand_id", "category_id", "description", "images",
                                        "variant_size", "images_size", "variant_name", "variants", "is_active",
                                        "created_at", "updated_at", "deleted_at"])
    live_cats = {c["id"] for c in cats}
    seen_slugs, seen_skus, notes = set(), set(), []
    for p in products:
        p["variants"] = json.loads(p["variants"] or "[]")
        slug = p["slug"] if SLUG.match(p["slug"] or "") else None
        if slug in seen_slugs:
            n = 2
            while "%s-%d" % (slug, n) in seen_slugs:
                n += 1
            notes.append("slug %s -> %s-%d (product %s)" % (slug, slug, n, p["id"]))
            slug = "%s-%d" % (slug, n)
        seen_slugs.add(slug)
        p["new_slug"] = slug
        for v in p["variants"]:
            if v["sku"] in seen_skus:
                notes.append("sku %s -> %s-dup (product %s, fix in admin)" % (v["sku"], v["sku"], p["slug"]))
                v["sku"] += "-dup"
            seen_skus.add(v["sku"])
        if p["category_id"] not in live_cats:
            notes.append("product %s: category %s is deleted, imported without category" % (p["slug"], p["category_id"]))
    return brands, cats, products, notes


def find_image(backup, slug, name):
    for d in ("product/" + slug, "temp"):
        path = os.path.join(backup, d, name)
        if name and os.path.isfile(path):
            return path
    return None


def images_of(backup, p):
    """[(path, legacy sku or None)], product images first, each file once."""
    out, seen = [], set()
    wanted = [(n.strip(), None) for n in (p["images"] or "").split(",")] + \
             [(v.get("image") or "", v["sku"]) for v in p["variants"]]
    for name, sku in wanted:
        if not name:
            continue
        path = find_image(backup, p["slug"], name)
        if path is None:
            raise SystemExit("missing image %s for %s" % (name, p["slug"]))
        if path not in seen:
            seen.add(path)
            out.append((path, sku))
    return out


# --- admin API ---------------------------------------------------------------------------------

class Api:
    def __init__(self, base, email, password):
        self.base, self.email, self.password, self.token = base.rstrip("/"), email, password, None

    def login(self):
        self.token = self._send("POST", "/auth/login", {"email": self.email, "password": self.password}, auth=False)["access_token"]

    def call(self, method, path, body=None, if_match=None):
        for _ in range(10):
            try:
                return self._send(method, path, body, if_match=if_match)
            except urllib.error.HTTPError as e:
                if e.code == 401:  # 15-minute token
                    self.login()
                elif e.code == 429:
                    time.sleep(int(e.headers.get("Retry-After") or 10))
                elif e.code >= 500:
                    time.sleep(5)
                else:
                    raise ApiError(method, path, e.code, e.read().decode("utf-8", "replace"))
        raise ApiError(method, path, 0, "gave up after 10 attempts")

    def _send(self, method, path, body, if_match=None, auth=True):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=None if body is None else json.dumps(body).encode())
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        if auth:
            req.add_header("Authorization", "Bearer " + self.token)
        if if_match is not None:
            req.add_header("If-Match", str(if_match))
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None


class ApiError(Exception):
    def __init__(self, method, path, status, body):
        super().__init__("%s %s -> %s %s" % (method, path, status, body))
        self.status = status


def put_object(url, path, mime):
    data = open(path, "rb").read()
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Content-Type", mime)
    urllib.request.urlopen(req, timeout=300).read()


# --- import ------------------------------------------------------------------------------------

def run(api, backup, brands, cats, products, state, save):
    b = state.setdefault("brands", {})
    for r in brands:
        if r["id"] not in b:
            b[r["id"]] = api.call("POST", "/brands", {"name": r["name"]})["id"]
            save()

    c = state.setdefault("categories", {})
    pending = [r for r in cats if r["id"] not in c]
    while pending:  # parents first
        ready = [r for r in pending if r["parent_id"] is None or r["parent_id"] in c]
        if not ready:
            raise SystemExit("category parents missing/cyclic: %s" % [r["id"] for r in pending])
        for r in ready:
            body = {"name": r["name"], "kind": "category"}
            if r["parent_id"]:
                body["parent_id"] = c[r["parent_id"]]
            c[r["id"]] = api.call("POST", "/categories", body)["id"]
            save()
        pending = [r for r in pending if r["id"] not in c]

    ps = state.setdefault("products", {})
    for i, p in enumerate(products, 1):
        st = ps.setdefault(p["id"], {})
        print("[%d/%d] %s" % (i, len(products), p["slug"]), flush=True)
        try:
            import_product(api, backup, p, st, b, c, save)
        except ApiError as e:
            st["error"] = str(e)
            save()
            print("   ! " + str(e), flush=True)


def import_product(api, backup, p, st, brands, cats, save):
    if "id" not in st:
        body = {"title": p["name"], "brand_id": brands[p["brand_id"]]}
        if p["description"]:
            body["description"] = p["description"].strip()
        if p["category_id"] in cats:
            body["category_ids"] = [cats[p["category_id"]]]
        st["id"] = api.call("POST", "/products", body)["id"]
        save()
    pid = st["id"]

    if "variants" not in st:
        sized = any(v["size"].strip() for v in p["variants"])
        rows = [{"option_values": [v["size"].strip()] if sized else [], "sku": v["sku"],
                 "regular_price": PRICE, "weight_grams": weight_grams(v["size"])} for v in p["variants"]]
        version = api.call("GET", "/products/" + pid)["version"]
        res = api.call("PUT", "/products/%s/variant-matrix" % pid, {
            "option_names": [p["variant_name"] or "Size"] if sized else [],
            "rows": rows, "archive_missing": False}, if_match=version)
        failed = [r for r in res["results"] if r["status"] == "error"]
        if failed:
            raise ApiError("PUT", "variant-matrix", 422, json.dumps(failed))
        st["variants"] = {row["sku"]: r["variant_id"] for row, r in zip(rows, res["results"])}
        save()

    done = st.setdefault("images", [])
    for path, sku in images_of(backup, p):
        if path in done:
            continue
        data = open(path, "rb").read()
        mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        pre = api.call("POST", "/media/presign", {"purpose": "product_image", "product_id": pid, "mime_type": mime,
                                                  "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        put_object(pre["upload_url"], path, mime)
        body = {"r2_key": pre["r2_key"], "product_id": pid}
        if sku:
            body["variant_id"] = st["variants"][sku]
        api.call("POST", "/media/confirm", body)
        done.append(path)
        save()

    if not st.get("published"):
        prod = api.call("GET", "/products/" + pid)
        body = {"status": "active"}
        if p["new_slug"] and prod["slug"] != p["new_slug"]:
            body["slug"] = p["new_slug"]
        try:
            api.call("PATCH", "/products/" + pid, body, if_match=prod["version"])
        except ApiError as e:
            if "slug" not in body or e.status != 422:
                raise
            st["slug_note"] = "kept %s: %s" % (prod["slug"], e)
            api.call("PATCH", "/products/" + pid, {"status": "active"}, if_match=prod["version"])
        st["published"] = True
        st.pop("error", None)
        save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", required=True, help="the acl-cosm-backup directory")
    ap.add_argument("--api", help="admin API base incl. /v1, e.g. https://api.example.com/v1")
    ap.add_argument("--state", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    backup = os.path.expanduser(a.backup)

    brands, cats, products, notes = load(backup)
    imgs = sum(len(images_of(backup, p)) for p in products)  # also fails fast on a missing file
    print("brands %d, categories %d, products %d, variants %d, images %d" % (
        len(brands), len(cats), len(products), sum(len(p["variants"]) for p in products), imgs))
    for n in notes:
        print("note: " + n)
    if a.dry_run:
        return
    if not a.api:
        ap.error("--api is required unless --dry-run")

    state = json.load(open(a.state)) if os.path.exists(a.state) else {}
    if state.get("api", a.api) != a.api:
        raise SystemExit("%s belongs to %s; use another --state" % (a.state, state["api"]))
    state["api"] = a.api

    def save():
        tmp = a.state + ".tmp"
        json.dump(state, open(tmp, "w"), indent=1)
        os.replace(tmp, a.state)

    api = Api(a.api, os.environ["ACL_EMAIL"], os.environ["ACL_PASSWORD"])
    api.login()
    run(api, backup, brands, cats, products, state, save)

    ps = state["products"].values()
    print("published %d/%d" % (sum(1 for s in ps if s.get("published")), len(products)))
    for lid, s in state["products"].items():
        if s.get("error") or s.get("slug_note"):
            print("product %s: %s" % (lid, s.get("error") or s["slug_note"]))
    sys.exit(1 if any(s.get("error") for s in ps) else 0)


if __name__ == "__main__":
    main()
