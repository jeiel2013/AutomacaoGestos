# gestures/__init__.py
# Marca a pasta como módulo Python.
# Importações centralizadas para facilitar o uso externo.

from .static  import classify as classify_static
from .dynamic import classify, update, update_two_hands, reset
