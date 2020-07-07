import logging
import math

from typing import Union, Dict, Set
from enum import Enum

import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer
from sc2.units import Units
from sc2.unit import Unit
from sc2.dicts.unit_trained_from import UNIT_TRAINED_FROM
from sc2.game_data import AbilityData, GameData, UnitTypeData
from sc2.data import race_worker
from sc2.data import race_townhalls
from sc2.data import Race
from sc2.position import Point2, Point3
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.constants import (
    IS_STRUCTURE,
    TERRAN_TECH_REQUIREMENT,
    PROTOSS_TECH_REQUIREMENT,
    ZERG_TECH_REQUIREMENT,
    EQUIVALENTS_FOR_TECH_PROGRESS,
    ALL_GAS
)

logger = logging.getLogger(__name__)

race_supplyUnit: Dict[Race, UnitTypeId] = {
    Race.Protoss: UnitTypeId.NOTAUNIT,
    Race.Terran: UnitTypeId.SUPPLYDEPOT,
    Race.Zerg: UnitTypeId.NOTAUNIT,
}

terranAddonBuildings = {UnitTypeId.BARRACKS, UnitTypeId.FACTORY, UnitTypeId.STARPORT}

class StartLocation(Enum):
    UNKNOWN = 1,
    BOTTOM_LEFT = 2,
    BOTTOM_RIGHT = 3,
    TOP_LEFT = 4,
    TOP_RIGHT = 5

class BuildListProcessBot(sc2.BotAI):

    def __init__(self, inputBuildList):
        self.buildList = inputBuildList
        self.currentTask = UnitTypeId.NOTAUNIT
        self.done = False
        self.startLocation = StartLocation.UNKNOWN
        self.gridStart: Point2 = Point2()

        # building grid
        self.maxColLength = 32
        # tells at which point the limit of a col in the grid is reached
        self.colStop = Point2((0, 0))
        self.plannedStructureSizes = dict()
        # tells how many cols there are 
        # also tells how many elements each of the following data structures has
        self.numberOfCols = 0
        # tells how wide each col is (double the building radius that can be placed in that col)
        self.colsWidths = []
        # tells where each col starts (Point2)
        self.colsStarts = []
        # tells the current build point within the cols (same as start point for now)
        self.colsNextBuildPoint = []

    def unitToId(self, unitName):
        if (unitName == "SupplyDepot"):
            return UnitTypeId.SUPPLYDEPOT
        if (unitName == "SCV"):
            return UnitTypeId.SCV
        if (unitName == "Barracks"):
            return UnitTypeId.BARRACKS
        if (unitName == "Marine"):
            return UnitTypeId.MARINE
        if (unitName == "Starport"):
            return UnitTypeId.STARPORT
        if (unitName == "Refinery"):
            return UnitTypeId.REFINERY
        if (unitName == "Factory"):
            return UnitTypeId.FACTORY
        return UnitTypeId.NOTAUNIT

    def checkAndAdvance(self):
        if not self.done:
            if self.currentTask == UnitTypeId.NOTAUNIT:
                if len(self.buildList) > 0:
                    # extract first build list element and set as current task
                    nextTaskName = self.buildList.pop(0)
                    self.currentTask = self.unitToId(nextTaskName)
                    logger.info("Beginning next task: " + nextTaskName + "(" + str(self.currentTask) + ")")
                else:
                    self.done = True

    def finishedCurrentTask(self):
        logger.info("Finished building: " + str(self.currentTask))
        self.currentTask = UnitTypeId.NOTAUNIT

    # simply check if a structure exists
    def structureExists(self, structureType : UnitTypeId):
        return self.structures.filter(lambda unit: unit.is_structure).exists
         
    def producedInTownhall(self, unitId):
        producers = UNIT_TRAINED_FROM[unitId]
        return any(x in race_townhalls[self.race] for x in producers)

    def builtByWorker(self, unitId):
        producers = UNIT_TRAINED_FROM[unitId]
        return race_worker[self.race] in producers

    def checkIfProducerExists(self, unitIdToProduce):
        # result is a pair of two bools
        # first bool: states if the producer exists
        # second bool: states if we can wait and it will be available later
        result = (False, False)
        
        producers = UNIT_TRAINED_FROM[unitIdToProduce]
        # check if the thing is produced by a SCV
        if self.builtByWorker(unitIdToProduce):
            # find workers
            workers: Units = self.workers.gathering
            if workers:
                result = (True, True)
            else:
                # are there any workers that are currently constructing stuff?
                workingWorkers = self.workers.filter(lambda unit: unit.is_constructing_scv)
                if workingWorkers:
                    # a worker will be available later
                    result = (False, True)
        else:
            # the unit or structure is build by a structure (trained or transformed)
            structuresToSearch = self.structures
            # if we use a townhall to build the thing we can use another (shorter) list than structures
            if self.producedInTownhall(unitIdToProduce):
                structuresToSearch = self.townhalls
            
            # filter all those that can built what we want to build
            structuresToSearch = structuresToSearch.filter(lambda structure: structure.type_id in producers)
            # filter all those that are ready
            structuresToSearch = structuresToSearch.ready

            if bool(structuresToSearch):
                # not empty
                # check if any of them has space in his build queue
                if any(structure.is_idle for structure in structuresToSearch):
                    result = (True, True)
                else: 
                    result = (False, True)
            else:
                # empty
                # check if any of the producers is pending
                if any(self.already_pending(producer) for producer in producers):
                    result = (False, True)
                else:
                    result = (False, False)

        return result

    # returns tuple: (canAfford, waitingHelps)
    # the results are:
    #   - (True, True): we have enough resources at the moment but waiting would also be fine
    #   - (False, True): we dont have enough resources right now but we can wait to fix that
    #   - (False, False): we dont have enogh resources right and waiting will not fix that
    # supply is only checked if it is of type UnitTypeId (probably always the case)
    def checkCosts(self, item_id: Union[UnitTypeId, UpgradeId, AbilityId]):
        cost = self.calculate_cost(item_id)

        minerals = (True, True)
        if cost.minerals > self.minerals:
            # not enough right now but maybe later?
            minerals = (False, True)
            # check if there are workers gathering minerals
            countMineralHarvestingWorkers = 0
            for townhall in self.townhalls:
                countMineralHarvestingWorkers += townhall.assigned_harvesters
            if countMineralHarvestingWorkers == 0:
                minerals = (False, False)
                logger.warn("There are not enough minerals to build: " + str(item_id))
        
        vespene = (True, True)
        if cost.vespene > self.vespene:
            # not enough right now but maybe later?
            vespene = (False, True)
            # check if there are workers harvesting vespene
            countVespeneHarvestingWorkers = 0
            for townhall in self.townhalls:
                countVespeneHarvestingWorkers += townhall.assigned_harvesters
            if countVespeneHarvestingWorkers == 0:
                vespene = (False, False)
                logger.warn("There is not enough vespene to build: " + str(item_id))

        supply = (True, True)
        supply_cost = self.calculate_supply_cost(item_id)
        # make sure this thing actually has supply cost
        if isinstance(item_id, UnitTypeId):
            if supply_cost and supply_cost > self.supply_left:
                # we dont have enough supply right now but maybe later?
                supply = (False, True)
                # check if supply building is being built
                # already pending checks everything: check its documentation
                if self.already_pending(UnitTypeId.SUPPLYDEPOT) == 0:
                    supply = (False, False)
                    logger.warn("There is not enough supply to build: " + str(item_id))

        return (minerals[0] and vespene[0] and supply[0], minerals[1] and vespene[1] and supply[1])

    def checkIfTechRequirementFulfilled(self, unitId):
        race_dict = {
            Race.Protoss: PROTOSS_TECH_REQUIREMENT,
            Race.Terran: TERRAN_TECH_REQUIREMENT,
            Race.Zerg: ZERG_TECH_REQUIREMENT,
        }
        # this gets the requirement for the unit we are checking
        requirement = race_dict[self.race][unitId]
        # if there is no requirement we can just skip the remaining stuff
        if UnitTypeId.NOTAUNIT == requirement:
            return (True, True)
        # 
        requirementEquivalents = {requirement}
        for equiv_structure in EQUIVALENTS_FOR_TECH_PROGRESS.get(requirement, []):
            requirementEquivalents.add(equiv_structure)

        correspondingStructures = self.structures.filter(lambda unit: unit.type_id in requirementEquivalents)

        # any of them already existing?
        fulfilled = bool(correspondingStructures.ready)
            
        # is any of these pending?
        # if yes waiting helps
        # waiting is also fine if it already exists
        waitingHelps = fulfilled
        if not fulfilled:
            waitingHelps = self.already_pending(requirement) > 0 

        return (fulfilled, waitingHelps)

    def checkPreconditions(self):
        # check if the producer exists or is under construction and if the producer is idle
        producerExists, canWaitProducer = self.checkIfProducerExists(self.currentTask)
        if not producerExists and not canWaitProducer:
            raise Exception("There must be a producer for " + str(self.currentTask))
        # check if we can afford the unit/structure
        resourcesExist, canWaitResources = self.checkCosts(self.currentTask) 
        if not resourcesExist and not canWaitResources:
            raise Exception("There are no SCVs left who are able to harvest resources to afford " + str(self.currentTask))
        # check if tech requirement is fullfilled only if the resources exist

        requirementFulfilled, canWaitRequirement = self.checkIfTechRequirementFulfilled(self.currentTask)
        if not requirementFulfilled and not canWaitRequirement:
            raise Exception("The requirement for " + str(self.currentTask) + " is not fullfilled!")

        # just return if we are able to build immediately --> if not that means we have to wait
        return producerExists and resourcesExist and requirementFulfilled

    def colHasSpaceLeft(self, index):
        width = self.colsWidths[index]
        spaceLeft = abs(self.colStop.y - self.colsNextBuildPoint[index].y)
        return spaceLeft >= width

    def advanceColsBuildPosition(self, index):
        if self.startLocation == StartLocation.TOP_LEFT or self.startLocation == StartLocation.TOP_RIGHT:
            # from top to bottom: -
            self.colsNextBuildPoint[index] = self.colsNextBuildPoint[index].offset((0, -self.colsWidths[index]))
        else:
            # from bottom to top: +
            self.colsNextBuildPoint[index] = self.colsNextBuildPoint[index].offset((0, self.colsWidths[index]))

    def getNextBuildPositionAndAdvance(self, unitId):
        unitTypeData: UnitTypeData = self.game_data.units[unitId.value]
        radius = unitTypeData.footprint_radius
        
        if unitId in terranAddonBuildings:
            radius += 1.0
        
        width = radius * 2.0

        for index in range(0, self.numberOfCols):
            # dont care about row if it does not match the width of my building
            if self.colsWidths[index] == width:
                if self.colHasSpaceLeft(index):
                    result = self.colsNextBuildPoint[index]
                    self.advanceColsBuildPosition(index)
                    return result

        raise Exception("No more build slots left!")

    def convertGridPositionToCenter(self, unitId: UnitTypeId, gridPosition: Point2):
        # get radius
        # important: only take actual size of building into account.
        # for a factory we  will not use the adapted size with an addon attached
        unitTypeData: UnitTypeData = self.game_data.units[unitId.value]
        radius = unitTypeData.footprint_radius
        result = gridPosition
        if self.startLocation == StartLocation.BOTTOM_LEFT:
            result = gridPosition.offset((radius, radius))
        elif self.startLocation == StartLocation.BOTTOM_RIGHT:
            result = gridPosition.offset((-radius, radius))
        elif self.startLocation == StartLocation.TOP_LEFT:
            result = gridPosition.offset((radius, -radius))
        elif self.startLocation == StartLocation.TOP_RIGHT:
            result = gridPosition.offset((-radius, -radius))
        else:
            raise Exception("Start location does not match one of four positions!")
    
        return result



    async def on_step(self, iteration: int):
        
        # always begin with checking and possibly advancing the buildlist
        self.checkAndAdvance()
        if not self.done:
            # next preconditions of the current task are checked
            ok = self.checkPreconditions()
            if ok:
                #built by worker or trained in building?
                if self.builtByWorker(self.currentTask):
                    workers: Units = self.workers.gathering
                    if workers:
                        worker: Unit = workers.furthest_to(workers.center)
                        gridPosition: Point2 = self.getNextBuildPositionAndAdvance(self.currentTask)

                        buildLocation: Point2 = self.convertGridPositionToCenter(self.currentTask,  gridPosition)

                        if self.can_place(self.currentTask, (buildLocation)):

                            worker.build(self.currentTask, buildLocation)

                            self.finishedCurrentTask()
                        else:
                            raise Exception("The provided build location is not valid!")

                else:
                    if self.producedInTownhall(self.currentTask):
                        self.townhalls.idle[0].train(self.currentTask)
                        self.finishedCurrentTask()
                    else:
                        unitsTrained = self.train(self.currentTask)
                        if unitsTrained == 0:
                            logger.info("could not train unit")
                        else:
                            self.finishedCurrentTask()


    async def on_start(self):

        if (self.game_info.player_start_location.x == 24.5):
            # left side of map
            if (self.game_info.player_start_location.y == 22.5):
                self.startLocation = StartLocation.BOTTOM_LEFT
                self.gridStart = self.game_info.player_start_location.offset((10, 10))
                self.colStop = self.gridStart.offset((0, 32))
            else:
                self.startLocation = StartLocation.TOP_LEFT
                self.gridStart = self.game_info.player_start_location.offset((10, -10))
                self.colStop = self.gridStart.offset((0, -32))
        else:
            # right side of map
            if (self.game_info.player_start_location.y == 22.5):
                self.startLocation = StartLocation.BOTTOM_RIGHT
                self.gridStart = self.game_info.player_start_location.offset((-10, 10))
                self.colStop = self.gridStart.offset((0, 32))
            else:
                self.startLocation = StartLocation.TOP_RIGHT
                self.gridStart = self.game_info.player_start_location.offset((-10, -10))
                self.colStop = self.gridStart.offset((0, -32))

        logger.info("Start location: " + str(self.startLocation))
        logger.info("Grid start: " + str(self.gridStart))

        # fill self.plannedStructureSizes
        for buildTask in self.buildList:
            unitId: UnitTypeId = self.unitToId(buildTask)
              
            unitTypeData: UnitTypeData = self.game_data.units[unitId.value]
            # if the building is a structure we store its footprint size
            if self.builtByWorker(unitId):
                
                # make sure it is not a gas bulilding and not a base building
                if not unitId in ALL_GAS:
                    if not unitId in race_townhalls[self.race]:
                        radius = unitTypeData.footprint_radius
                        # in case this is a building that might have an addon
                        if unitId in terranAddonBuildings:
                            # increase radius by 1 to safe space for possible addons
                            radius += 1
                        logger.info("Adding " + str(unitId) + " to structure sizes with radius " + str(radius))
                        if radius in self.plannedStructureSizes:
                            self.plannedStructureSizes[radius] += 1
                        else:
                            self.plannedStructureSizes[radius] = 1


        offsetBetweenCols = Point2((1, 0))
        if self.startLocation == StartLocation.BOTTOM_RIGHT:
            offsetBetweenCols = Point2((-1, 0))
        if self.startLocation == StartLocation.TOP_LEFT:
            offsetBetweenCols = Point2((1, 0))
        if self.startLocation == StartLocation.TOP_RIGHT:
            offsetBetweenCols = Point2((-1, 0))

        # iteration variables
        currentColStart = self.gridStart

        for radius, count in self.plannedStructureSizes.items():
            
            # compute how many cols are necessary
            buildingsPerCol = self.maxColLength // (radius * 2) 
            colsNecessary = math.ceil(count / buildingsPerCol)

            self.numberOfCols += colsNecessary

            self.colsWidths.append(radius * 2)

            self.colsStarts.append(Point2(currentColStart))

            # needs a copy
            self.colsNextBuildPoint.append(Point2(currentColStart))
            

            # offset given by width of building
            if self.startLocation == StartLocation.BOTTOM_LEFT or self.startLocation == StartLocation.TOP_LEFT:
                currentColStart = currentColStart.offset((radius*2, 0))
            else:
                currentColStart = currentColStart.offset((radius * (-2), 0))
            # extra offset to have some space in between cols
            currentColStart = currentColStart.offset(offsetBetweenCols)


        logger.info("Finished grid stuff!")
        logger.info("Number of cols: " + str(self.numberOfCols))
        logger.info("Cols widths: " + str(self.colsWidths))
        logger.info("colsStarts: " + str(self.colsStarts))
        logger.info("cols next build points: " + str(self.colsNextBuildPoint))


            
        
        






# TODO: special build locations für vespene und base
# TODO: redistribute workers
# TODO: turn if in unitToId to dict lookup





# starting the bot
# one enemy just for first testing
buildListInput = ["SCV", "SupplyDepot", "Barracks", "Barracks", "SupplyDepot", "SupplyDepot", "Factory", "Barracks"]

run_game(maps.get("Flat128"), [
    Bot(Race.Terran, BuildListProcessBot(buildListInput)),
    Computer(Race.Protoss, Difficulty.VeryEasy)
], realtime=True)