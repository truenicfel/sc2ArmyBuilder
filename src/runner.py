from BuildListProcessBotZerg import BuildListProcessBotZerg
from BuildListProcessBotTerran import BuildListProcessBotTerran
from BuildListProcessBotBase import Player

from sc2.player import Bot, Computer
from sc2 import run_game, maps, Race, Difficulty

# zerg build lists:
#   - all structures
buildListInputAllStructures = ["Drone", "Drone", "SpawningPool", "Extractor", "EvolutionChamber", "RoachWarren", "Drone", "Drone", "Drone", "Drone", "Extractor", "Lair", "HydraliskDen", "InfestationPit", "LurkerDenMP", "Spire", "Hive", "UltraliskCavern", "GreaterSpire"]
#   - zergling
buildListOneZergling = ["Drone", "Drone", "Overlord", "SpawningPool", "Zergling"]
#   - ten roaches
buildListTenRoaches = ["Drone", "Drone", "Overlord", "SpawningPool", "Drone", "Drone", "RoachWarren", "Extractor", "Drone", "Drone", "Overlord", "Hatchery", "Overlord", "Roach", "Roach", "Roach", "Roach", "Roach", "Roach", "Roach", "Roach", "Roach", "Roach"]

# terran build lists:
#   - unknown
buildListInputOne = ["SCV", "SupplyDepot", "Refinery", "Barracks", "Refinery", "Factory", "SupplyDepot", "SCV", "Starport", "SCV", "StarportTechLab", "FusionCore", "Battlecruiser"]
#   - unknown
buildListInputTwo = ["SCV", "SupplyDepot", "Barracks", "SCV", "Refinery", "Barracks", "SCV", "SupplyDepot", "SCV", "BarracksReactor", "Marine", "Marine", "Marine", "Barracks", "BarracksReactor", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine"]
#   - single marine
buildListOneMarine = ["SCV", "SCV", "SupplyDepot", "Barracks", "Marine"]
#   - two marines
buildListTwoMarines = ["SCV", "SCV", "SupplyDepot", "Barracks", "Marine", "Marine"]
#   - thor simple (4:33)
buildListThorSimple = ["SCV", "SCV", "SupplyDepot", "Barracks", "Refinery", "Factory", "FactoryTechLab", "EngineeringBay", "Armory", "Thor"]
#   - thor economy
buildListThorEconomy = ["SCV", "SCV", "SupplyDepot", "Barracks", "Refinery", "SCV", "SCV", "SCV", "SupplyDepot", "Factory", "Refinery", "FactoryTechLab", "EngineeringBay", "Armory", "Thor"]
#   - mix marine marauder
buildListMarineMarauder = ["SCV", "SCV", "SupplyDepot", "Barracks", "Refinery", "SCV", "SCV", "SCV", "SupplyDepot", "Barracks", "BarracksTechLab", "Marine", "Marine", "Marine", "BarracksTechLab", "Marauder", "Marine", "Marauder", "SupplyDepot", "Marauder", "Marine", "Marauder", "Marauder"]

run_game(maps.get("Flat128"), [
    Bot(Race.Zerg, BuildListProcessBotZerg(buildListTenRoaches.copy(), Player.PLAYER_ONE), name="ZergOne"),
    Bot(Race.Terran, BuildListProcessBotTerran(buildListMarineMarauder.copy(), Player.PLAYER_TWO), name="ZergTwo")
    #Computer(Race.Protoss, Difficulty.Medium)
], realtime=True)