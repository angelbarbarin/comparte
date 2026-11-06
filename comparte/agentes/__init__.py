"""Los cuatro agentes de ComParte. Solo el orquestador (``comparte/orquestador.py``) los coordina.

* ``captador``    – conversa con el donante y estructura la donación (CP-01, CP-02).
* ``coordinador`` – elige al receptor óptimo y reasigna si rechaza (CP-03, CP-04).
* ``logistico``   – elige voluntario, calcula la ruta y da seguimiento (CP-05).
* ``impacto``     – calcula kg, raciones, personas y CO2e; genera reportes (CP-07, CP-08).
"""
