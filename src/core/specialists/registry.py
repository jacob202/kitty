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
from .news import NewsFeedSpecialist

SPECIALISTS = {
    "Alex": AlexAudioSpecialist("Alex", "audio", "data/knowledge_bases/audio/"),
    "Mike": MikeAutomotiveSpecialist("Mike", "automotive", "data/knowledge_bases/automotive/"),
    "KittyCoder": KittyCoderSpecialist("KittyCoder", "code", "data/knowledge_bases/code/"),
    "Avery": AveryCreativeSpecialist("Avery", "creative", "data/knowledge_bases/creative/"),
    "Jonny": JonnyDesignSpecialist("Jonny", "design", "data/knowledge_bases/design/"),
    "Kelly": KellyFitnessSpecialist("Kelly", "fitness", "data/knowledge_bases/fitness/"),
    "Taylor": TaylorGrowthSpecialist("Taylor", "growth", "data/knowledge_bases/growth/"),
    "Morgan": MorganInfrastructureSpecialist("Morgan", "infrastructure", "data/knowledge_bases/infrastructure/"),
    "KnowledgeAcquisition": KnowledgeAcquisitionSpecialist("KnowledgeAcquisition", "knowledge_acquisition", "data/knowledge_bases/knowledge_acquisition/"),
    "Rowan": RowanResearchSpecialist("Rowan", "research", "data/knowledge_bases/research/"),
    "Kitty": KittySoulSpecialist("Kitty", "general", ""),
    "News": NewsFeedSpecialist("News", "news", "data/knowledge_bases/news/"),
}

def get_specialist(name: str):
    return SPECIALISTS.get(name)

def list_specialists():
    return list(SPECIALISTS.keys())
