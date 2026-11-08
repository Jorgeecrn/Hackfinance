"""Evalúa Centinela sobre un conjunto de mensajes etiquetados.

Uso (desde la raíz del repo):
    python eval/run_eval.py --modo reglas        # sin IA, instantáneo, gratis
    python eval/run_eval.py --modo ia            # agente con Claude (necesita ANTHROPIC_API_KEY)
    python eval/run_eval.py --modo ia --limite 20

Un mensaje cuenta como «marcado» si el nivel es amarillo o rojo.
Escribe un informe en eval/resultados_<modo>.md.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import state as st  # noqa: E402
from app.config import settings  # noqa: E402
from app.rules import analyze_rules  # noqa: E402

CONTACTS = st.SEED["contactos"]
FAMILY = st.SEED["perfil"]["familiar"]


def load_dataset(limit: int | None) -> list[dict]:
    rows = [json.loads(line) for line in (ROOT / "eval" / "dataset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:limit] if limit else rows


async def classify_ia(row: dict) -> tuple[str, int]:
    from app.agent import investigate

    rules = analyze_rules(row["texto"], row["remitente"], CONTACTS)
    async for ev in investigate(row["texto"], row["remitente"], row["canal"], rules, CONTACTS, FAMILY):
        if ev["tipo"] == "veredicto":
            return ev["datos"]["nivel"], ev["datos"]["puntuacion"]
    raise RuntimeError("sin veredicto")


async def run(mode: str, limit: int | None, concurrency: int) -> None:
    rows = load_dataset(limit)
    sem = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async def one(row):
        async with sem:
            t0 = time.perf_counter()
            try:
                if mode == "reglas":
                    r = analyze_rules(row["texto"], row["remitente"], CONTACTS)
                    level, score = r.level, r.score
                else:
                    level, score = await classify_ia(row)
                err = None
            except Exception as exc:  # se cuenta como error y se informa
                level, score, err = "error", 0, str(exc)
            ms = (time.perf_counter() - t0) * 1000
            results.append({**row, "nivel": level, "puntuacion": score, "ms": ms, "error": err})
            mark = "✓" if (level in ("amarillo", "rojo")) == (row["etiqueta"] == "estafa") else "✗"
            print(f"{mark} #{row['id']:>3} {row['etiqueta']:<9} -> {level:<8} ({ms:,.0f} ms) {row['texto'][:60]}")

    await asyncio.gather(*[one(r) for r in rows])
    results.sort(key=lambda r: r["id"])
    report(mode, results)


def report(mode: str, results: list[dict]) -> None:
    valid = [r for r in results if r["nivel"] != "error"]
    tp = sum(1 for r in valid if r["etiqueta"] == "estafa" and r["nivel"] != "verde")
    fn = sum(1 for r in valid if r["etiqueta"] == "estafa" and r["nivel"] == "verde")
    fp = sum(1 for r in valid if r["etiqueta"] == "legitimo" and r["nivel"] != "verde")
    tn = sum(1 for r in valid if r["etiqueta"] == "legitimo" and r["nivel"] == "verde")
    red_scams = sum(1 for r in valid if r["etiqueta"] == "estafa" and r["nivel"] == "rojo")
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    fpr = fp / (fp + tn) if fp + tn else 0
    acc = (tp + tn) / len(valid) if valid else 0
    lat = sorted(r["ms"] for r in valid)
    p50 = statistics.median(lat) if lat else 0
    p95 = lat[int(0.95 * (len(lat) - 1))] if lat else 0
    errors = [r for r in results if r["nivel"] == "error"]
    wrong = [r for r in valid if (r["nivel"] != "verde") != (r["etiqueta"] == "estafa")]

    model = settings.claude_model if mode == "ia" else "—"
    lines = [
        f"# Resultados de evaluación — modo `{mode}`",
        "",
        f"- Mensajes: **{len(results)}** ({sum(r['etiqueta'] == 'estafa' for r in results)} estafas, {sum(r['etiqueta'] == 'legitimo' for r in results)} legítimos)",
        f"- Modelo: `{model}` · esfuerzo: `{settings.claude_effort if mode == 'ia' else '—'}`",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Precisión (de lo que marcamos, cuánto era estafa) | **{precision:.1%}** |",
        f"| Recall (de las estafas, cuántas detectamos) | **{recall:.1%}** |",
        f"| F1 | **{f1:.2f}** |",
        f"| Exactitud | {acc:.1%} |",
        f"| Falsas alarmas sobre mensajes legítimos | {fpr:.1%} ({fp} de {fp + tn}) |",
        f"| Estafas marcadas en ROJO | {red_scams} de {tp + fn} |",
        f"| Latencia mediana / p95 | {p50:,.0f} ms / {p95:,.0f} ms |",
        f"| Errores | {len(errors)} |",
        "",
        "Matriz de confusión (marcado = amarillo o rojo):",
        "",
        "| | Marcado | No marcado |",
        "|---|---|---|",
        f"| **Estafa** | {tp} | {fn} |",
        f"| **Legítimo** | {fp} | {tn} |",
        "",
    ]
    if wrong:
        lines += ["## Fallos", "", "| # | Etiqueta | Nivel | Mensaje |", "|---|---|---|---|"]
        lines += [f"| {r['id']} | {r['etiqueta']} | {r['nivel']} | {r['texto'][:90].replace('|', '/')} |" for r in wrong]
    if errors:
        lines += ["", "## Errores", ""] + [f"- #{r['id']}: {r['error']}" for r in errors]
    out = ROOT / "eval" / f"resultados_{mode}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines[:18]))
    print(f"\nInforme completo: {out.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["reglas", "ia"], default="reglas")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--concurrencia", type=int, default=4)
    args = ap.parse_args()
    if args.modo == "ia" and not settings.claude_enabled:
        sys.exit("El modo ia necesita ANTHROPIC_API_KEY en el .env (y FORCE_OFFLINE desactivado).")
    asyncio.run(run(args.modo, args.limite, args.concurrencia if args.modo == "ia" else 1))


if __name__ == "__main__":
    main()
