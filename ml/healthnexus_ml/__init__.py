"""Health Nexus machine-learning package.

Three model families, matching the product spec:

* ``models.triage``   — model 1: the general health-guidance assistant.
* ``models.wellness`` — model 2: the premium daily diet / movement / lifestyle plan.
* ``models.ranker``   — model 3: the doctor, hospital, lab, pharmacy and
  insurance recommenders.

``service`` exposes all three over HTTP in the shape the FastAPI product
backend already expects (see ``backend/app/services/ml_client.py``).
"""

__version__ = "1.0.0"
