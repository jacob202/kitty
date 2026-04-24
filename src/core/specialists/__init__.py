"""Specialist implementations."""

from .audio import AlexAudioSpecialist
from .automotive import MikeAutomotiveSpecialist
from .code import KittyCoderSpecialist
from .creative import AveryCreativeSpecialist
from .design import JonnyDesignSpecialist
from .fitness import KellyFitnessSpecialist
from .growth import TaylorGrowthSpecialist
from .infrastructure import MorganInfrastructureSpecialist
from .knowledge_acquisition import KnowledgeAcquisitionSpecialist
from .research import RowanResearchSpecialist
from .soul import KittySoulSpecialist

__all__ = [
    "KittySoulSpecialist",
    "KnowledgeAcquisitionSpecialist",
    "AlexAudioSpecialist",
    "AveryCreativeSpecialist",
    "KellyFitnessSpecialist",
    "MikeAutomotiveSpecialist",
    "MorganInfrastructureSpecialist",
    "TaylorGrowthSpecialist",
    "KittyCoderSpecialist",
    "JonnyDesignSpecialist",
    "RowanResearchSpecialist",
]
