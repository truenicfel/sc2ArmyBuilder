from BuildListProcessBotZerg import BuildListProcessBotZerg
from BuildListProcessBotTerran import BuildListProcessBotTerran
from BuildListProcessBotBase import Player

from sc2.player import Bot, Computer
from sc2 import run_game, maps, Race, Difficulty

buildListInputAllStructures = ["Drone", "Drone", "SpawningPool", "Extractor", "EvolutionChamber", "RoachWarren", "Drone", "Drone", "Drone", "Drone", "Extractor", "Lair", "HydraliskDen", "InfestationPit", "LurkerDenMP", "Spire", "Hive", "UltraliskCavern", "GreaterSpire"]
buildListInputZergling = ["Drone", "Drone", "Overlord", "SpawningPool", "Zergling"]

# starting the bot
# one enemy just for first testing
buildListInputOne = ["SCV", "SupplyDepot", "Refinery", "Barracks", "Refinery", "Factory", "SupplyDepot", "SCV", "Starport", "SCV", "StarportTechLab", "FusionCore", "Battlecruiser"]
buildListInputTwo = ["SCV", "SupplyDepot", "Barracks", "SCV", "Refinery", "Barracks", "SCV", "SupplyDepot", "SCV", "BarracksReactor", "Marine", "Marine", "Marine", "Barracks", "BarracksReactor", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine", "Marine"]
buildListMarine = ["SCV", "SCV", "SupplyDepot", "Barracks", "Marine"]


run_game(maps.get("Flat128"), [
    Bot(Race.Zerg, BuildListProcessBotZerg(buildListInputZergling.copy(), Player.PLAYER_ONE), name="ZergBot"),
    Bot(Race.Terran, BuildListProcessBotTerran(buildListMarine.copy(), Player.PLAYER_TWO), name="TerranBot")
    #Computer(Race.Protoss, Difficulty.Medium)
], realtime=True)