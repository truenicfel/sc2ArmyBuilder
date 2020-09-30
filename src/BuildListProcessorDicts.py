from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2

from enum import Enum
from typing import Union, Dict, Set

TERRAN_STRUCTURE_UPGRADES: Dict[AbilityId, Set[UnitTypeId]] = {

    AbilityId.BUILD_REACTOR_BARRACKS: {UnitTypeId.BARRACKS},
    AbilityId.BUILD_TECHLAB_BARRACKS: {UnitTypeId.BARRACKS}

}

class StartLocation(Enum):
    UNKNOWN = 1,
    BOTTOM_LEFT = 2,
    BOTTOM_RIGHT = 3,
    TOP_LEFT = 4,
    TOP_RIGHT = 5

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
    "Drone": UnitTypeId.DRONE,
    "Overlord": UnitTypeId.OVERLORD,
    "SpawningPool": UnitTypeId.SPAWNINGPOOL,
    "EvolutionChamber": UnitTypeId.EVOLUTIONCHAMBER,
    "RoachWarren": UnitTypeId.ROACHWARREN,
    "Extractor": UnitTypeId.EXTRACTOR,
    "BanelingNest": UnitTypeId.BANELINGNEST,
    "Lair": UnitTypeId.LAIR,
    "HydraliskDen": UnitTypeId.HYDRALISKDEN,
    "InfestationPit": UnitTypeId.INFESTATIONPIT,
    "LurkerDenMP": UnitTypeId.LURKERDENMP,
    "Spire": UnitTypeId.SPIRE,
    "Hive": UnitTypeId.HIVE,
    "UltraliskCavern": UnitTypeId.ULTRALISKCAVERN,
    "SpineCrawler": UnitTypeId.SPINECRAWLER,
    "NydusNetwork": UnitTypeId.NYDUSNETWORK,
    "SporeCrawler": UnitTypeId.SPORECRAWLER,
    "GreaterSpire": UnitTypeId.GREATERSPIRE,
    "Queen": UnitTypeId.QUEEN,
    "Zergling": UnitTypeId.ZERGLING,
    "Overseer": UnitTypeId.OVERSEER,
    "Baneling": UnitTypeId.BANELING,
    "Viper": UnitTypeId.VIPER,
    "Hydralisk": UnitTypeId.HYDRALISK,
    "Infestor": UnitTypeId.INFESTOR,
    "Mutalisk": UnitTypeId.MUTALISK,
    "Roach": UnitTypeId.ROACH,
    "Ravager": UnitTypeId.RAVAGER,
    "Larva": UnitTypeId.LARVA,
    "LurkerMP": UnitTypeId.LURKERMP,
    "Corruptor": UnitTypeId.CORRUPTOR,
    "Ultralisk": UnitTypeId.ULTRALISK,
    "Broodlord": UnitTypeId.BROODLORD,
    "Hatchery": UnitTypeId.HATCHERY
}

BASE_BUILDINGS = {
    UnitTypeId.BARRACKSREACTOR: {UnitTypeId.BARRACKS},
    UnitTypeId.BARRACKSTECHLAB: {UnitTypeId.BARRACKS},
    UnitTypeId.FACTORYREACTOR: {UnitTypeId.FACTORY},
    UnitTypeId.FACTORYTECHLAB: {UnitTypeId.FACTORY},
    UnitTypeId.STARPORTREACTOR: {UnitTypeId.STARPORT},
    UnitTypeId.STARPORTTECHLAB: {UnitTypeId.STARPORT}
}

ZERG_BUILD_LOCATIONS: Dict[UnitTypeId, Dict[StartLocation, Point2]] = {
    UnitTypeId.SPAWNINGPOOL: {
        StartLocation.BOTTOM_LEFT: Point2((28.5, 19.5)),
        StartLocation.BOTTOM_RIGHT: Point2((123.5, 19.5)),
        StartLocation.TOP_LEFT: Point2((28.5, 128.5)),
        StartLocation.TOP_RIGHT: Point2((123.5, 128.5))
    },
    UnitTypeId.EVOLUTIONCHAMBER: {
        StartLocation.BOTTOM_LEFT: Point2((28.5, 22.5)),
        StartLocation.BOTTOM_RIGHT: Point2((123.5, 22.5)),
        StartLocation.TOP_LEFT: Point2((28.5, 125.5)),
        StartLocation.TOP_RIGHT: Point2((123.5, 125.5))
    },
    UnitTypeId.ROACHWARREN: {
        StartLocation.BOTTOM_LEFT: Point2((28.5, 25.5)),
        StartLocation.BOTTOM_RIGHT: Point2((123.5, 25.5)),
        StartLocation.TOP_LEFT: Point2((28.5, 122.5)),
        StartLocation.TOP_RIGHT: Point2((123.5, 122.5))
    },
    UnitTypeId.BANELINGNEST: {
        StartLocation.BOTTOM_LEFT: Point2((28.5, 28.5)),
        StartLocation.BOTTOM_RIGHT: Point2((123.5, 29.5)),
        StartLocation.TOP_LEFT: Point2((28.5, 119.5)),
        StartLocation.TOP_RIGHT: Point2((123.5, 119.5))
    },
    UnitTypeId.HYDRALISKDEN: {
        StartLocation.BOTTOM_LEFT: Point2((25.5, 28.5)),
        StartLocation.BOTTOM_RIGHT: Point2((126.5, 29.5)),
        StartLocation.TOP_LEFT: Point2((25.5, 119.5)),
        StartLocation.TOP_RIGHT: Point2((126.5, 119.5))
    },
    UnitTypeId.INFESTATIONPIT: {
        StartLocation.BOTTOM_LEFT: Point2((22.5, 28.5)),
        StartLocation.BOTTOM_RIGHT: Point2((129.5, 29.5)),
        StartLocation.TOP_LEFT: Point2((22.5, 119.5)),
        StartLocation.TOP_RIGHT: Point2((129.5, 119.5))
    },
    UnitTypeId.LURKERDENMP: {
        StartLocation.BOTTOM_LEFT: Point2((19.5, 28.5)),
        StartLocation.BOTTOM_RIGHT: Point2((132.5, 29.5)),
        StartLocation.TOP_LEFT: Point2((19.5, 119.5)),
        StartLocation.TOP_RIGHT: Point2((132.5, 119.5))
    },
    UnitTypeId.SPIRE: {
        StartLocation.BOTTOM_LEFT: Point2((31.5, 19.5)),
        StartLocation.BOTTOM_RIGHT: Point2((120.5, 19.5)),
        StartLocation.TOP_LEFT: Point2((31.5, 128.5)),
        StartLocation.TOP_RIGHT: Point2((120.5, 128.5))
    },
    UnitTypeId.ULTRALISKCAVERN: {
        StartLocation.BOTTOM_LEFT: Point2((31.5, 22.5)),
        StartLocation.BOTTOM_RIGHT: Point2((120.5, 22.5)),
        StartLocation.TOP_LEFT: Point2((31.5, 125.5)),
        StartLocation.TOP_RIGHT: Point2((120.5, 125.5))
    },
    
}
