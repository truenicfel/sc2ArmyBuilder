from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId

from typing import Union, Dict, Set

TERRAN_STRUCTURE_UPGRADES: Dict[AbilityId, Set[UnitTypeId]] = {

    AbilityId.BUILD_REACTOR_BARRACKS: {UnitTypeId.BARRACKS},
    AbilityId.BUILD_TECHLAB_BARRACKS: {UnitTypeId.BARRACKS}

}

CONVERT_TO_ID = {
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
    "FusionCore": UnitTypeId.FUSIONCORE
}

BASE_BUILDINGS = {
    UnitTypeId.BARRACKSREACTOR: {UnitTypeId.BARRACKS},
    UnitTypeId.BARRACKSTECHLAB: {UnitTypeId.BARRACKS},
    UnitTypeId.FACTORYREACTOR: {UnitTypeId.FACTORY},
    UnitTypeId.FACTORYTECHLAB: {UnitTypeId.FACTORY},
    UnitTypeId.STARPORTREACTOR: {UnitTypeId.STARPORT},
    UnitTypeId.STARPORTTECHLAB: {UnitTypeId.STARPORT}
}