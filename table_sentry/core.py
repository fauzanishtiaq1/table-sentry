"""Deterministic, read-only diagnostics for tabular files."""
from __future__ import annotations
import csv, hashlib, json, math, re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence
import unicodedata

MISSING = "missing:"

def _decimal_token(value):
    # Normalize by tuple manipulation, never Decimal.normalize (context rounding).
    if value == 0:
        return "number:0"
    sign, digits, exponent = value.as_tuple()
    digits = list(digits)
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    return "number:" + ("-" if sign else "") + ''.join(map(str, digits)) + "e" + str(exponent)

@dataclass(frozen=True)
class ScanOptions:
    target: str | None = None
    id_columns: tuple[str, ...] = ()
    time_column: str | None = None
    group_columns: tuple[str, ...] = ()
    overlap_keys: tuple[str, ...] = ()
    association_threshold: float = 0.98
    sample_limit: int = 20

def _canon(v: Any) -> str:
    if v is None: return MISSING
    if isinstance(v, str):
        s = unicodedata.normalize("NFC", v)
        if s == "": return "missing:"
        try:
            d = Decimal(s)
            if d.is_finite():
                return _decimal_token(d)
        except InvalidOperation: pass
        return "string:" + s
    if isinstance(v, bool): return "bool:true" if v else "bool:false"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if isinstance(v, float) and not math.isfinite(v): return "number:" + str(v)
        d=Decimal(str(v)); return _decimal_token(d)
    return "other:" + unicodedata.normalize("NFC", str(v))

def _hash(vals: Sequence[Any]) -> str:
    b = bytearray()
    for v in vals:
        x = _canon(v).encode("utf-8"); b.extend(len(x).to_bytes(8, "big")); b.extend(x)
    return hashlib.sha256(bytes(b)).hexdigest()

def _read(path: str | Path):
    p=Path(path); ext=p.suffix.lower()
    if ext not in (".csv", ".jsonl", ".ndjson"): raise ValueError("unsupported extension")
    try:
        if ext == ".csv":
            with p.open("r", encoding="utf-8", newline="") as f:
                rd=csv.DictReader(f); headers=rd.fieldnames
                if not headers or any(not h for h in headers) or len(set(headers)) != len(headers): raise ValueError("invalid CSV header at line 1")
                rows=[]
                for n,r in enumerate(rd,2):
                    if None in r or any(v is None for v in r.values()): raise ValueError(f"invalid CSV row at line {n}")
                    rows.append(dict(r))
            return rows, list(headers), "csv"
        rows=[]; keys=None
        with p.open("r", encoding="utf-8") as f:
            for n,line in enumerate(f,1):
                if not line.strip(): continue
                try: obj=json.loads(line)
                except json.JSONDecodeError as e: raise ValueError(f"invalid JSONL at line {n}") from e
                if not isinstance(obj,dict): raise ValueError(f"JSONL record at line {n} is not an object")
                ks=set(obj)
                if keys is None: keys=ks
                elif ks != keys: raise ValueError(f"inconsistent JSONL keys at line {n}")
                rows.append(obj)
        return rows, sorted(keys or set()), "jsonl"
    except OSError as e: raise ValueError(str(e)) from e

def _finding(kind, severity, message, evidence, recommendation, col=""):
    return {"id": f"{kind}:{col}" if col else kind, "kind":kind, "severity":severity, "message":message, "evidence":evidence, "recommendation":recommendation}

def _numeric(v):
    try:
        s=v if isinstance(v,str) and v.startswith("number:") else _canon(v)
        if not s.startswith("number:"): return None
        d=Decimal(s[7:]); f=float(d); return f if math.isfinite(f) else None
    except (InvalidOperation, ValueError, OverflowError): return None

def _corr(xs, ys):
    n=len(xs); sx=max(max(abs(x) for x in xs), max(abs(y) for y in ys), 1.0)
    xx=[x/sx for x in xs]; yy=[y/sx for y in ys]; mx=sum(xx)/n; my=sum(yy)/n
    a=sum((x-mx)**2 for x in xx); b=sum((y-my)**2 for y in yy)
    if a <= 0 or b <= 0: return None
    c=sum((x-mx)*(y-my) for x,y in zip(xx,yy))
    return c / math.sqrt(a*b)

def scan_file(path: str | Path, options: ScanOptions = ScanOptions()) -> dict[str, Any]:
    if not isinstance(options, ScanOptions) or not isinstance(options.association_threshold,(int,float)) or not 0 <= options.association_threshold <= 1 or options.sample_limit < 0:
        raise ValueError("invalid scan options")
    rows, cols, fmt = _read(path); findings=[]; warnings=[]
    for c in options.id_columns + options.group_columns + ((options.target,) if options.target else ()) + ((options.time_column,) if options.time_column else ()):
        if c and c not in cols: raise ValueError(f"missing column: {c}")
    if options.group_columns:
        groups={}
        for r in rows: groups.setdefault(tuple(_canon(r.get(c)) for c in options.group_columns),0); groups[tuple(_canon(r.get(c)) for c in options.group_columns)]+=1
        evidence={"group_columns":list(options.group_columns),"group_count":len(groups),"max_group_rows":max(groups.values(),default=0)}
    else: evidence={}
    keys=[_hash([r.get(c) for c in cols]) for r in rows]; counts=Counter(keys); dup={k:n for k,n in counts.items() if n>1}
    if dup: findings.append(_finding("duplicate_rows","warning", "Exact duplicate rows detected", {"duplicate_row_count":sum(n-1 for n in dup.values()),"unique_duplicated_keys":len(dup),**evidence}, "Review duplicate records and provenance."))
    for c in cols:
        miss=sum(_canon(r.get(c))==MISSING for r in rows)
        if miss: findings.append(_finding("missingness","info",f"Missing values in {c}",{"column":c,"missing_count":miss,"row_count":len(rows)},"Review whether missingness is expected.",c))
    if options.target:
        target=[_canon(r.get(options.target)) for r in rows]
        for c in cols:
            if c==options.target: continue
            pairs=[(_canon(r.get(c)),t) for r,t in zip(rows,target) if _canon(r.get(c))!=MISSING and t!=MISSING]
            if len(pairs)>=20 and len(set(t for _,t in pairs))>=2:
                mp={};
                for x,t in pairs: mp.setdefault(x,set()).add(t)
                # Require repeated feature values and functional mapping; unique identifiers are not useful evidence.
                if len(set(x for x,_ in pairs)) < len(pairs) and all(len(v)==1 for v in mp.values()):
                    findings.append(_finding("suspicious_association","warning",f"{c} uniquely determines target in complete rows",{"column":c,"target":options.target,"complete_pairs":len(pairs),"association_type":"unique_categorical"},"Investigate target leakage; this heuristic is not proof.",c))
                xs=[_numeric(x) for x,t in pairs]; ys=[_numeric(t) for x,t in pairs]
                if len(pairs) >= 30 and all(x is not None for x in xs) and all(y is not None for y in ys):
                    corr=_corr(xs,ys)
                    if corr is not None and abs(corr)>=options.association_threshold:
                        findings.append(_finding("suspicious_association","warning",f"{c} has strong numeric association with target",{"column":c,"target":options.target,"complete_pairs":len(pairs),"pearson_correlation":corr},"Investigate target leakage; this heuristic is not proof.",c))
    if options.time_column:
        last={}; bad=0; out=0
        for i,r in enumerate(rows):
            raw=r.get(options.time_column); dt=None
            try:
                if _numeric(raw) is not None: dt=datetime.fromtimestamp(_numeric(raw),timezone.utc)
                else: dt=datetime.fromisoformat(str(raw).replace("Z","+00:00"))
                if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            except (ValueError,TypeError,OSError,OverflowError): bad+=1; continue
            g=tuple(_canon(r.get(c)) for c in options.group_columns)
            if g in last and dt < last[g]: out+=1
            last[g]=dt
        if out or bad: findings.append(_finding("temporal_order","warning","Temporal values require review",{"column":options.time_column,"out_of_order_rows":out,"unparseable_count":bad},"Review chronological ordering and split strategy."))
    findings.sort(key=lambda x:(x["kind"],x["evidence"].get("column", ""),x["id"]))
    return {"schema_version":"1.0","tool":"table-sentry","input":{"path":Path(path).name,"format":fmt,"row_count":len(rows),"columns":cols},"summary":{"finding_count":len(findings),"severity_counts":{s:sum(f["severity"]==s for f in findings) for s in ("info","warning","error")},"completed_at_utc":datetime.now(timezone.utc).isoformat()},"findings":findings,"warnings":warnings}

def compare_splits(train: str | Path, test: str | Path, options: ScanOptions = ScanOptions()) -> dict[str, Any]:
    tr,tc,tf=_read(train); te,ec,ef=_read(test)
    keys=list(options.overlap_keys) if options.overlap_keys else sorted(set(tc)&set(ec))
    if not keys: raise ValueError("no overlap keys")
    if any(k not in tc or k not in ec for k in keys): raise ValueError("missing overlap key")
    a=[_hash([r.get(k) for k in keys]) for r in tr]; b=[_hash([r.get(k) for k in keys]) for r in te]; sa=set(a); sb=set(b); overlap=sa&sb
    findings=[]
    if overlap: findings.append(_finding("split_overlap","warning","Canonical keys overlap between splits",{"key_columns":keys,"overlap_count":len(overlap),"train_matching_rows":sum(x in overlap for x in a),"test_matching_rows":sum(x in overlap for x in b)},"Review split construction and provenance."))
    return {"schema_version":"1.0","tool":"table-sentry","input":{"path":Path(test).name,"format":ef,"row_count":len(te),"columns":ec},"splits":{"train_row_count":len(tr),"test_row_count":len(te)},"overlap":{"key_columns":keys,"overlap_count":len(overlap),"overlap_rate":len(overlap)/len(sb) if sb else 0.0},"summary":{"finding_count":len(findings),"severity_counts":{"info":0,"warning":len(findings),"error":0},"completed_at_utc":datetime.now(timezone.utc).isoformat()},"findings":findings,"warnings":[]}

def render_json(result: Mapping[str, Any], *, indent: int = 2) -> str:
    return json.dumps(result, indent=indent, ensure_ascii=False, sort_keys=True, allow_nan=False)
