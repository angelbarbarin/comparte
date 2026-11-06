"""Mide la precisión de estructuración del Agente Captador sobre mensajes etiquetados.

    python scripts/evaluar_captador.py                 # motor de reglas (gratis, sin internet)
    python scripts/evaluar_captador.py --motor claude  # requiere ANTHROPIC_API_KEY; hace ~40 llamadas (con costo)

La meta del documento de visión es >= 90 %. Ver comparte/evaluacion.py para la definición exacta.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comparte.config import obtener_ajustes  # noqa: E402
from comparte.evaluacion import evaluar_extractor  # noqa: E402
from comparte.llm.reglas import ExtractorReglas  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--motor", choices=["reglas", "claude"], default="reglas")
    args = parser.parse_args()

    if args.motor == "claude":
        ajustes = obtener_ajustes()
        if not ajustes.api_key:
            print("Falta ANTHROPIC_API_KEY (ver .env.example).", file=sys.stderr)
            return 2
        from comparte.llm.claude import ExtractorClaude

        extractor = ExtractorClaude(ajustes.api_key, ajustes.modelo_claude)
        print(f"Motor: claude ({ajustes.modelo_claude}). Se harán llamadas reales a la API.")
    else:
        extractor = ExtractorReglas()
        print("Motor: reglas")

    resultado = evaluar_extractor(extractor)
    print(f"\nExactitud total: {resultado.correctos}/{resultado.total} = {100 * resultado.exactitud:.1f} % (meta: >= 90 %)")
    for lote, (ok, total) in sorted(resultado.por_lote.items()):
        nota = ("con el que se corrigió el motor (optimista)" if lote == "A"
                else "escrito después de las correcciones (menos sesgado)")
        print(f"  Lote {lote}: {ok}/{total} = {100 * ok / total:.1f} %  <- {nota}")
    print()
    for f in resultado.fallos:
        print(f"✗ [{f.lote}] {f.texto}\n    esperado: {f.esperado}\n    obtenido: {f.obtenido}")
    # La referencia honesta es el lote B (el A se usó para arreglar el motor).
    return 0 if resultado.exactitud_lote("B") >= 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
