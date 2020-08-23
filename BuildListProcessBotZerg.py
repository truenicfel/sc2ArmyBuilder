from BuildListProcessBotBase import (
    BuildListProcessBotBase,
    Player,
    StartLocation,
    race_supplyUnit
)
import logging
from sc2.player import Bot, Computer
from sc2 import run_game, maps, Race, Difficulty
from sc2.position import Point2
from sc2.units import Units
from sc2.unit import Unit
from sc2.constants import (
    IS_STRUCTURE
)
from sc2.ids.unit_typeid import UnitTypeId
from sc2.game_data import UnitTypeData
from BuildListProcessorDicts import ZERG_BUILD_LOCATIONS


# Class
# ----------------------------------------

class BuildListProcessBotZerg(BuildListProcessBotBase):

    # Constructor
    # ----------------------------------------

    def __init__(self, inputBuildList, player: Player):
        # base class
        BuildListProcessBotBase.__init__(self, inputBuildList, player)
        # logger
        self.loggerChild = logging.getLogger("BuildListProcessBotZerg" + self.playerString)
        # the place where the last building was placed
        self.lastBuildLocation = Point2((0, 0))

    # Startup preparation
    # ----------------------------------------

    # startup routine. Should prepare:
    #   - enemy location
    #   - build postitions for buildings
    async def on_start(self):
        # call base to handle enemy location
        BuildListProcessBotBase.onStartBase(self)
        self.lastBuildLocation = self.game_info.player_start_location
        if self.startLocation == StartLocation.BOTTOM_LEFT:
            self.lastBuildLocation = self.lastBuildLocation.offset((2.0, 2.0))
        if self.startLocation == StartLocation.BOTTOM_RIGHT:
            self.lastBuildLocation = self.lastBuildLocation.offset((-2.0, 2.0))
        if self.startLocation == StartLocation.TOP_LEFT:
            self.lastBuildLocation = self.lastBuildLocation.offset((2.0, -2.0))
        if self.startLocation == StartLocation.TOP_RIGHT:
            self.lastBuildLocation = self.lastBuildLocation.offset((-2.0, -2.0)) 
        return

    def scanBuildList(self):
        # call base
        BuildListProcessBotBase.scanBuildList(self)
        # scan build list for spore crawler, nydus network or spine crawler
        # which dont make sense in this scenario
        buildListCopy = self.buildList.copy()

        forbiddenBuildings = {UnitTypeId.NYDUSNETWORK, UnitTypeId.SPORECRAWLER, UnitTypeId.SPINECRAWLER}

        for element in buildListCopy:
            unitId: UnitTypeId = self.unitToId(element)
            if unitId in forbiddenBuildings:
                raise Exception(str(unitId) + " is not allowed for this bot!")
            
        self.loggerChild.info("BuildList has no errors.")

    def raceSpecificUnitAndStructureCreations(self):
        # one overlord is created initially
        self.remainingBuildTasks[UnitTypeId.OVERLORD] = 1

    def raceSpecificUnitCompletedIgnore(self, unit: UnitTypeId):
        # ignore if unit is larva
        return unit == UnitTypeId.LARVA

    def raceSpecificStructureCompletedIgnore(self, unit: UnitTypeId):
        # nothing to ignore
        return False

    # Build Locations
    # ----------------------------------------

    def getBuildLocationForCurrentTask(self):
        return ZERG_BUILD_LOCATIONS[self.currentTask][self.startLocation]

    # Building
    # ----------------------------------------

    def buildStructure(self):
        
        # structures for zerg can either be morphed from drones or from existing buildings
        # if its morphed from a drone we need a building location otherwise not
        # special cases for building locations: hatchery and extractor

        # get producers and producer ids first
        producers: Units = self.getProducerUnitsForCurrentTask()
        producerIds = self.getProducerIdsForCurrentTask()

        if any(self.isWorker(producerId) for producerId in producerIds):

            # special cases: refinery and command centers:
            if self.currentTask == UnitTypeId.EXTRACTOR: 
                result = self.buildGasBuilding()
                if result:
                    self.finishedCurrentTask()
                else:
                    raise Exception("Could not build gas building because there was no build location found!")
            elif self.currentTask == UnitTypeId.HATCHERY:
                raise Exception("Not implemented yet")
            else:

                # building location needed
                buildLocation: Point2 = self.getBuildLocationForCurrentTask()
                producer: Unit = self.getWorker(buildLocation)
                self.loggerChild.info("Calling build with " + str(self.currentTask) + " and " + str(buildLocation))
                result = producer.build(self.currentTask, buildLocation)
                if result:
                    self.finishedCurrentTask()
                else:
                    self.loggerChild.info("Even though all preconditions were fulfilled " + str(self.currentTask) + " could not be built!")
        else:
            producer: Unit = producers.random
            # produce!
            result = producer.train(self.currentTask, queue=False, can_afford_check=True)
            if result:
                self.finishedCurrentTask()
            else:
                self.loggerChild.info("Even though all preconditions were fulfilled " + str(self.currentTask) + " could not be built!")

    def trainUnit(self):
        # need no building location just produce a unit from the producer
        # get the producers
        possibleProducers: Units = self.getProducerUnitsForCurrentTask()
        producers: Units = possibleProducers.idle + possibleProducers.gathering
        if producers:
            # select one of them randomly 
            # TODO: is there a better way to do this?
            producer: Unit = producers.random
            # produce!
            result = producer.train(self.currentTask)
            if result:
                self.finishedCurrentTask()
            else:
                self.loggerChild.info("Even though all preconditions were fulfilled " + str(self.currentTask) + " could not be trained!")

    # Run
    # ----------------------------------------

    def attackMapCenterWithArmy(self):
        attackPoint = self.game_info.map_center
        army: Units = self.units.filter(lambda unit: not (unit.type_id == UnitTypeId.DRONE or unit.type_id == UnitTypeId.OVERLORD or unit.type_id == UnitTypeId.LARVA))
        for unit in army:
            unit.attack(attackPoint)

    def zergOnStep(self):

        # checking preconditions...
        # checks:
        #   - can afford (supply, minerals, vespene)
        #   - tech requirement
        #   - producer available
        ok: bool = self.checkPreconditions()
        # if necessarry more conditions can be checked next

        if ok:
            # next check if the result is a structure or a unit
            taskInfo: UnitTypeData = self.game_data.units[self.currentTask.value]

            if IS_STRUCTURE in taskInfo.attributes:
                
                self.buildStructure()

            else:

                self.trainUnit()

    async def on_step(self, iteration: int):
        # base does some more preparation -> only do something if base returns true
        if BuildListProcessBotBase.onStepBase(self, iteration):
            # TODO: fix for worker not being built problem?
            # did not fix it

            if iteration % 5 == 0:
                # do business here
                self.zergOnStep()
            pass

buildListInputAllStructures = ["Drone", "Drone", "SpawningPool", "Extractor", "EvolutionChamber", "RoachWarren", "Drone", "Drone", "Drone", "Drone", "Extractor", "Lair", "HydraliskDen", "InfestationPit", "LurkerDenMP", "Spire", "Hive", "UltraliskCavern", "GreaterSpire"]
buildListInputOne = ["Drone", "Drone", "Overlord", "SpawningPool", "Extractor", "Drone", "Drone", "Extractor", "Drone", "Drone", "Overlord", "RoachWarren", "Overlord", "Roach", "Roach", "Roach", "Roach", "Roach"]
run_game(maps.get("Flat128"), [
    Bot(Race.Zerg, BuildListProcessBotZerg(buildListInputOne.copy(), Player.PLAYER_ONE), name="PlayerOne"),
    Bot(Race.Zerg, BuildListProcessBotZerg(buildListInputOne.copy(), Player.PLAYER_TWO), name="PlayerTwo")
    #Computer(Race.Protoss, Difficulty.Medium)
], realtime=True)