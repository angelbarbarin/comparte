"""ComParte: plataforma agéntica de rescate de alimentos (ODS 2, Hambre cero).

Paquete principal del backend. Convenciones del proyecto:

* El dominio de negocio está en español (Donante, Receptor, Voluntario, Donacion...),
  igual que en el documento de visión y en los diagramas UML.
* La infraestructura técnica (config, db, api) usa nombres convencionales en inglés/español neutro.
* Cada agente vive en ``comparte/agentes/`` y solo el orquestador los coordina.
"""

__version__ = "0.1.0"
