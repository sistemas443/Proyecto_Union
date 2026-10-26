# models/talento_humano/__init__.py
# Paquete de modelos para Talento Humano

from .colaborador import Colaborador
from .capacitaciones import Capacitacion
from .experiencia import Experiencia
from .familiares import Familiar
from .maestros import EPS, ARL

__all__ = ['Colaborador', 'Capacitacion', 'Experiencia', 'Familiar', 'EPS', 'ARL']