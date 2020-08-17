from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId

from typing import Union, Dict, Set

TERRAN_STRUCTURE_UPGRADES: Dict[AbilityId, Set[UnitTypeId]] = {

    AbilityId.BUILD_REACTOR_BARRACKS: {UnitTypeId.BARRACKS},
    AbilityId.BUILD_TECHLAB_BARRACKS: {UnitTypeId.BARRACKS}

}

CONVERT_TO_ID = {
    # TERRAN:
    "SCV": UnitTypeId.SCV,
    "SupplyDepot": UnitTypeId.SUPPLYDEPOT,
    "Barracks": UnitTypeId.BARRACKS,
    "Marine": UnitTypeId.MARINE,
    "Starport": UnitTypeId.STARPORT,
    "Refinery": UnitTypeId.REFINERY,
    "Factory": UnitTypeId.FACTORY,
    "CommandCenter": UnitTypeId.COMMANDCENTER,
    "Medivac": UnitTypeId.MEDIVAC,
    "BarracksTechLab": UnitTypeId.BARRACKSTECHLAB,
    "BarracksReactor": UnitTypeId.BARRACKSREACTOR,
    "FactoryReactor": UnitTypeId.FACTORYREACTOR, 
    "FactoryTechLab": UnitTypeId.FACTORYTECHLAB,
    "StarportTechLab": UnitTypeId.STARPORTTECHLAB,
    "StarportReactor": UnitTypeId.STARPORTREACTOR,
    "Battlecruiser": UnitTypeId.BATTLECRUISER,
    "FusionCore": UnitTypeId.FUSIONCORE,
    "OrbitalCommand": UnitTypeId.ORBITALCOMMAND,
    "PlanetaryFortress": UnitTypeId.PLANETARYFORTRESS,
    "EngineeringBay": UnitTypeId.ENGINEERINGBAY,
    "MissileTurret": UnitTypeId.MISSILETURRET,
    "GhostAcademy": UnitTypeId.GHOSTACADEMY,
    "Reaper": UnitTypeId.REAPER,
    "Armory": UnitTypeId.ARMORY,
    "Bunker": UnitTypeId.BUNKER,
    "Marauder": UnitTypeId.MARAUDER,
    "SensorTower": UnitTypeId.SENSORTOWER,
    "SiegeTank": UnitTypeId.SIEGETANK,
    "Ghost": UnitTypeId.GHOST,
    "Thor": UnitTypeId.THOR,
    "WidowMine": UnitTypeId.WIDOWMINE,
    "Banshee": UnitTypeId.BANSHEE,
    "Hellion": UnitTypeId.HELLION,
    "VikingFighter": UnitTypeId.VIKINGFIGHTER,
    "HellionTank": UnitTypeId.HELLIONTANK,
    "Cyclone": UnitTypeId.CYCLONE,
    "Liberator": UnitTypeId.LIBERATOR,
    "Raven": UnitTypeId.RAVEN,

    # ZERG:
    "Drone": UnitTypeId.DRONE
}

BASE_BUILDINGS = {
    UnitTypeId.BARRACKSREACTOR: {UnitTypeId.BARRACKS},
    UnitTypeId.BARRACKSTECHLAB: {UnitTypeId.BARRACKS},
    UnitTypeId.FACTORYREACTOR: {UnitTypeId.FACTORY},
    UnitTypeId.FACTORYTECHLAB: {UnitTypeId.FACTORY},
    UnitTypeId.STARPORTREACTOR: {UnitTypeId.STARPORT},
    UnitTypeId.STARPORTTECHLAB: {UnitTypeId.STARPORT}
}
