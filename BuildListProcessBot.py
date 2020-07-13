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
from sc2.data import race_gas
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

class Player(Enum):
    PLAYER_ONE = 1,
    PLAYER_TWO = 2


class BuildListProcessBot(sc2.BotAI):

    def __init__(self, inputBuildList, player: Player):
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

        # expansion stuff
        self.player: Player = player
        self.expansionLocationsComputed = False
        self.bottomExpansions = list()
        self.topExpansions = list()
        self.leftExpansions = list()
        self.rightExpansions = list()

        self.expansionLocations = list()

        BuildListProcessBot.PLAYER_ONE_START_LOCATION: StartLocation = StartLocation.UNKNOWN
        BuildListProcessBot.PLAYER_TWO_START_LOCATION: StartLocation = StartLocation.UNKNOWN


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
        if (unitName == "CommandCenter"):
            return UnitTypeId.COMMANDCENTER
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
            # at least some workers and
            if len(self.workers) > 10 and len(self.townhalls) > 0:
                minerals = (False, True)
            else:
                minerals = (False, False)
                logger.warn("There are not enough minerals to build " + str(item_id) + " and waiting does not help!")
        
        vespene = (True, True)
        if cost.vespene > self.vespene:
            # not enough right now but maybe later?
            if len(self.workers) > 10 and len(self.gas_buildings.ready) + self.already_pending(race_gas[self.race]):
                # waiting helps
                vespene = (False, True)
            else:
                vespene = (False, False)
                logger.warn("There is not enough vespene to build " + str(item_id) + " and waiting does not help!")

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

    # finds an appropriate worker (closest to position or unit)
    def getWorker(self, position: Union[Unit, Point2, Point3]):
        workersGathering: Units = self.workers.gathering

        if workersGathering:
            # select worker closest to pos or unit
            return workersGathering.closest_to(position)
        else:
            raise Exception("There are no gathering workers which could be used to build " + self.currentTask)

    def buildRefinery(self):
        # cant build more gas buildings than townhalls
        # TODO: evaluate this condition
        if len(self.gas_buildings.ready) + self.already_pending(self.currentTask) < len(self.townhalls) * 2:
            
            # prefer townhalls that are ready
            for townhall in self.townhalls.ready:
                # all vespene geysers closer than distance ten to the current townhall
                vespeneGeysers: Units  = self.vespene_geyser.closer_than(10, townhall)
                logger.info("Found " + str(len(vespeneGeysers)) + " vespene geyser locations!")
                # check all locations
                for vespeneGeyser in vespeneGeysers:
                    if self.can_place(self.currentTask, (vespeneGeyser.position)):
                        worker: Unit = self.getWorker(vespeneGeyser)
                        worker.build_gas(vespeneGeyser)
                        return True
            # townhalls that are not ready
            for townhall in self.townhalls.not_ready:
                # all vespene geysers closer than distance ten to the current townhall
                vespeneGeysers: Units  = self.vespene_geyser.closer_than(10, townhall)
                logger.info("Found " + str(len(vespeneGeysers)) + " vespene geyser locations!")
                # check all locations
                for vespeneGeyser in vespeneGeysers:
                    if self.can_place(self.currentTask, (vespeneGeyser.position)):
                        worker: Unit = self.getWorker(vespeneGeyser)
                        worker.build_gas(vespeneGeyser)
                        return True

        else:
            raise Exception("Per townhall 2 vespene buildings allowed!")

    def buildBase(self):
        if bool(self.expansionLocations):
            location: Point2 = self.expansionLocations.pop(0)
            worker: Unit = self.workers.gathering.closest_to(location)
            if self.can_place(self.currentTask, location):
                worker.build(self.currentTask, location)
            else:
                raise Exception("could not build the command center where it was supposed to be built!")
        else:
            raise Exception("No more places to build command expansions!")

    def myWorkerDistribution(self):

        # Shamelessly stolen from: https://github.com/BurnySc2/python-sc2/blob/develop/examples/terran/mass_reaper.py
        # ---------------------------------------------

        mineralTags = [x.tag for x in self.mineral_field]
        gas_buildingTags = [x.tag for x in self.gas_buildings]

        workerPool = Units([], self)
        workerPoolTags = set()

        # # Find all gas_buildings that have surplus or deficit
        deficit_gas_buildings = {}
        surplusgas_buildings = {}
        for g in self.gas_buildings.filter(lambda x: x.vespene_contents > 0):
            # Only loop over gas_buildings that have still gas in them
            deficit = g.ideal_harvesters - g.assigned_harvesters
            if deficit > 0:
                deficit_gas_buildings[g.tag] = {"unit": g, "deficit": deficit}
            elif deficit < 0:
                surplusWorkers = self.workers.closer_than(10, g).filter(
                    lambda w: w not in workerPoolTags
                    and len(w.orders) == 1
                    and w.orders[0].ability.id in [AbilityId.HARVEST_GATHER]
                    and w.orders[0].target in gas_buildingTags
                )
                for i in range(-deficit):
                    if surplusWorkers.amount > 0:
                        w = surplusWorkers.pop()
                        workerPool.append(w)
                        workerPoolTags.add(w.tag)
                surplusgas_buildings[g.tag] = {"unit": g, "deficit": deficit}

        # # Find all townhalls that have surplus or deficit
        deficitTownhalls = {}
        surplusTownhalls = {}
        for th in self.townhalls:
            deficit = th.ideal_harvesters - th.assigned_harvesters
            if deficit > 0:
                deficitTownhalls[th.tag] = {"unit": th, "deficit": deficit}
            elif deficit < 0:
                surplusWorkers = self.workers.closer_than(10, th).filter(
                    lambda w: w.tag not in workerPoolTags
                    and len(w.orders) == 1
                    and w.orders[0].ability.id in [AbilityId.HARVEST_GATHER]
                    and w.orders[0].target in mineralTags
                )
                # workerPool.extend(surplusWorkers)
                for i in range(-deficit):
                    if surplusWorkers.amount > 0:
                        w = surplusWorkers.pop()
                        workerPool.append(w)
                        workerPoolTags.add(w.tag)
                surplusTownhalls[th.tag] = {"unit": th, "deficit": deficit}
        
        # ---------------------------------------------

        # We now know which building has a deficit and which one has a surplus. If a building has a surplus
        # the workers are added to the worker pool. Whenever we have anything in the worker pool we want to
        # distribute those first.

        if bool(workerPool):

            # iterate deficit townhalls
            for townhallTag, info in deficitTownhalls.items():
                # get the minerals close to the current townhall
                mineralFields: Units = self.mineral_field.closer_than(10, info["unit"])
                # if there are any
                if mineralFields:
                    # get the deficit (missing worker to optimal performance)
                    deficit = info["deficit"]
                    # check if the worker pool does contain anything
                    workersLeft = bool(workerPool)
                    # if there is a deficit move one worker to the townhall from the worker pool
                    if deficit > 0 and workersLeft:
                        worker: Unit = workerPool.pop()
                        mineralField: Unit = mineralFields.closest_to(worker)
                        logger.info("Moving one worker to harvest minerals at " + str(info["unit"]))
                        if len(worker.orders) == 1 and worker.orders[0].ability.id in [AbilityId.HARVEST_RETURN]:
                            worker.gather(mineralField, queue=True)
                        else:
                            worker.gather(mineralField)
            # iterate deficit gas buildings
            for gasTag, info in deficit_gas_buildings.items():
                # get the deficit (missing worker to optimal performance)
                deficit = info["deficit"]
                # check if the worker pool does contain anything
                workersLeft = bool(workerPool)
                # if there is a deficit move one worker to the townhall from the worker pool
                if deficit > 0 and workersLeft:
                    worker: Unit = workerPool.pop()
                    logger.info("Moving one worker to harvest gas at " + str(info["unit"]))
                    if len(worker.orders) == 1 and worker.orders[0].ability.id in [AbilityId.HARVEST_RETURN]:
                        worker.gather(info["unit"], queue=True)
                    else:
                        worker.gather(info["unit"])
        else:
            # Whenever we do not have worker in the worker pool we want to move some workers to harvest gas but only if a certain ratio between
            # total vespene workers and total mineral workers is not exceeded.

            totalMineralWorkers = 0
            totalVespeneWorkers = 0

            for townhall in self.townhalls.ready:
                totalMineralWorkers += townhall.assigned_harvesters
            for gasBuilding in self.gas_buildings.ready:
                totalVespeneWorkers += gasBuilding.assigned_harvesters

            # only if less than 33% workers are on vespene
            if (totalVespeneWorkers / (totalMineralWorkers + totalVespeneWorkers)) < 0.34:
                for gasTag, info in deficit_gas_buildings.items():
                    worker: Unit = self.workers.gathering.closest_to(info["unit"].position)
                    logger.info("Moving one worker to " + str(info["unit"]))
                    if len(worker.orders) == 1 and worker.orders[0].ability.id in [AbilityId.HARVEST_RETURN]:
                        worker.gather(info["unit"], queue=True)
                    else:
                        worker.gather(info["unit"])
        
        # redistribute idle workers
        if len(self.workers.idle) > 0:
            if self.townhalls:
                for worker in self.workers.idle:
                    townhall: Unit = self.townhalls.closest_to(worker)
                    mineralFields: Units = self.mineral_field.closer_than(10, townhall)
                    if mineralFields:
                        mineralField: Unit = mineralFields.closest_to(worker)
                        worker.gather(mineralField)

        

        # logger.info("Worker pool:")
        # logger.info(str(workerPool))

        # logger.info("deficit townhalls:")
        # logger.info(str(deficitTownhalls))

        # logger.info("deficit gas:")
        # logger.info(str(deficit_gas_buildings))

        # logger.info("surplus townhalls:")
        # logger.info(str(surplusTownhalls))

        # logger.info("surplus gas:")
        # logger.info(str(surplusgas_buildings))

    def getCorrespondingStartLocation(self, point: Point2):
        if (point[0] == 24.5):
            # left side of map
            if (point[1] == 22.5):
                return StartLocation.BOTTOM_LEFT
            else:
                return StartLocation.TOP_LEFT
        else:
            # right side of map
            if (point[1] == 22.5):
                return StartLocation.BOTTOM_RIGHT
            else:
                return StartLocation.TOP_RIGHT
    
    def getLocationFromStartLocation(self, startLocation: StartLocation):
        if startLocation == StartLocation.BOTTOM_LEFT:
            return Point2((24.5, 22.5))
        if startLocation == StartLocation.BOTTOM_RIGHT:
            return Point2((127.5, 22.5))
        if startLocation == StartLocation.TOP_RIGHT:
            return Point2((127.5, 125.5))
        if startLocation == StartLocation.TOP_LEFT:
            return Point2((24.5, 125.5))
        raise Exception("Location is not a start location! " + str(startLocation))
        
    def findNextExpansion(self, current: Point2, ccwDirection: bool):
        # first need to check if current is one of the start locations
        # "corners of map"
        if current in self.game_info.start_locations + [self.game_info.player_start_location]:
            correspondingStartLocation = self.getCorrespondingStartLocation(current)
            if (correspondingStartLocation == StartLocation.UNKNOWN):
                raise Exception("Could not find start location for " + str(current))
            if ccwDirection:
                if correspondingStartLocation == StartLocation.BOTTOM_LEFT:
                    return self.bottomExpansions[1] # they are sorted from low to high x so this is fine
                if correspondingStartLocation == StartLocation.BOTTOM_RIGHT:
                    return self.rightExpansions[1]
                if correspondingStartLocation == StartLocation.TOP_RIGHT:
                    return self.topExpansions[len(self.topExpansions) - 2]
                if correspondingStartLocation == StartLocation.TOP_LEFT:
                    return self.leftExpansions[len(self.leftExpansions) - 2]
            else:
                # cw direction
                if correspondingStartLocation == StartLocation.BOTTOM_LEFT:
                    return self.leftExpansions[1]
                if correspondingStartLocation == StartLocation.BOTTOM_RIGHT:
                    return self.bottomExpansions[len(self.bottomExpansions) - 2]
                if correspondingStartLocation == StartLocation.TOP_RIGHT:
                    return self.rightExpansions[len(self.rightExpansions) - 2]
                if correspondingStartLocation == StartLocation.TOP_LEFT:
                    return self.topExpansions[1]
        else:
            # not in one of the corners
            if current in self.bottomExpansions:
                index = self.bottomExpansions.index(current)
                if ccwDirection:
                    # go right
                    return self.bottomExpansions[index+1]
                else:
                    # go left
                    return self.bottomExpansions[index-1]
            if current in self.rightExpansions:
                index = self.rightExpansions.index(current)
                if ccwDirection:
                    return self.rightExpansions[index+1]
                else:
                    return self.rightExpansions[index-1]
            if current in self.topExpansions:
                index = self.topExpansions.index(current)
                if ccwDirection:
                    return self.topExpansions[index-1]
                else:
                    return self.topExpansions[index+1]
            if current in self.leftExpansions:
                index = self.leftExpansions.index(current)
                if ccwDirection:
                    return self.leftExpansions[index-1]
                else:
                    return self.leftExpansions[index+1]
        
    def computeExpansionLocations(self):
        possibleExpansionLocations = set()

        # add all expansions including player start locations to the set
        for expansionLocation in self.expansion_locations_list:
            possibleExpansionLocations.add(expansionLocation)

        for expansionLocation in possibleExpansionLocations:
            # the bottom row of expansions is roughly at 22.5
            # use a threshhold to ensure every single one is in
            if abs(expansionLocation[1] - 22.5) < 2.0: 
                self.bottomExpansions.append(expansionLocation)
        self.bottomExpansions.sort(key=lambda x: x[0])

        for expansionLocation in possibleExpansionLocations:
            # the top row of expansions is roughly at 125.5
            # use a threshhold to ensure every single one is in
            if abs(expansionLocation[1] - 125.5) < 2.0: 
                self.topExpansions.append(expansionLocation)
        self.topExpansions.sort(key=lambda x: x[0])

        for expansionLocation in possibleExpansionLocations:
            # the left column of expansions is roughly at 24.5
            # use a threshhold to ensure every single one is in
            if abs(expansionLocation[0] - 24.5) < 2.0: 
                self.leftExpansions.append(expansionLocation)
        self.leftExpansions.sort(key=lambda x: x[1])

        for expansionLocation in possibleExpansionLocations:
            # the right column of expansions is roughly at 24.5
            # use a threshhold to ensure every single one is in
            if abs(expansionLocation[0] - 127.5) < 2.0: 
                self.rightExpansions.append(expansionLocation)
        self.rightExpansions.sort(key=lambda x: x[1])

        # there is always two directions in which we could go to find expansions:
        # in ccw and in cw direction
        # we always prefer ccw direction but alternate between the two to stay close to our main

        # my side:
        # --------------------

        playerOnePreferredExpansionCCWDirection = list()
        playerOnePreferredExpansionCWDirection = list()

        currentCCW: Point2 = self.getLocationFromStartLocation(BuildListProcessBot.PLAYER_ONE_START_LOCATION)
        currentCW: Point2 = currentCCW

        currentCCW = self.findNextExpansion(currentCCW, True)
        currentCW = self.findNextExpansion(currentCW, False)

        while currentCW != currentCCW:
            # store
            playerOnePreferredExpansionCCWDirection.append(currentCCW)
            playerOnePreferredExpansionCWDirection.append(currentCW)
            # advance
            currentCCW = self.findNextExpansion(currentCCW, True)
            currentCW = self.findNextExpansion(currentCW, False)
        
        # append one last time
        playerOnePreferredExpansionCCWDirection.append(currentCCW)
        playerOnePreferredExpansionCWDirection.append(currentCW)

        # opponents side side:
        # --------------------

        playerTwoPreferredExpansionCCWDirection = list()
        playerTwoPreferredExpansionCWDirection = list()

        currentCCW: Point2 = self.getLocationFromStartLocation(BuildListProcessBot.PLAYER_TWO_START_LOCATION)
        currentCW: Point2 = currentCCW

        currentCCW = self.findNextExpansion(currentCCW, True)
        currentCW = self.findNextExpansion(currentCW, False)

        while currentCW != currentCCW:
            # store
            playerTwoPreferredExpansionCCWDirection.append(currentCCW)
            playerTwoPreferredExpansionCWDirection.append(currentCW)
            # advance
            currentCCW = self.findNextExpansion(currentCCW, True)
            currentCW = self.findNextExpansion(currentCW, False)
        
        # append one last time
        playerTwoPreferredExpansionCCWDirection.append(currentCCW)
        playerTwoPreferredExpansionCWDirection.append(currentCW)

        # now of both players the preferences of expansions in both possible directions are known
        
        # remove both start locations from possibleExpansionLocations
        possibleExpansionLocations.remove(self.getLocationFromStartLocation(BuildListProcessBot.PLAYER_ONE_START_LOCATION))
        possibleExpansionLocations.remove(self.getLocationFromStartLocation(BuildListProcessBot.PLAYER_TWO_START_LOCATION))

        playerOneExpansionLocations = list()
        playerTwoExpansionLocations = list()

        # ccw direction is always taken first
        ccwRoundPlayerOne = True
        ccwRoundPlayerTwo = True
        while bool(possibleExpansionLocations):
            # player one goes first
            if ccwRoundPlayerOne:  
                playerOneSelectedExpansion = playerOnePreferredExpansionCCWDirection.pop(0)
                if playerOneSelectedExpansion in possibleExpansionLocations:
                    playerOneExpansionLocations.append(playerOneSelectedExpansion)
                    possibleExpansionLocations.remove(playerOneSelectedExpansion)
                    ccwRoundPlayerOne = False
                else:
                    playerOneSelectedExpansion = playerOnePreferredExpansionCWDirection.pop(0)
                    if playerOneSelectedExpansion in possibleExpansionLocations:
                        playerOneExpansionLocations.append(playerOneSelectedExpansion)
                        possibleExpansionLocations.remove(playerOneSelectedExpansion)
                        ccwRoundPlayerOne = True
                    else:
                        raise Exception("There are no expansion locations left for player one even though there is still locations available!")
            else:
                playerOneSelectedExpansion = playerOnePreferredExpansionCWDirection.pop(0)
                if playerOneSelectedExpansion in possibleExpansionLocations:
                    playerOneExpansionLocations.append(playerOneSelectedExpansion)
                    possibleExpansionLocations.remove(playerOneSelectedExpansion)
                    ccwRoundPlayerOne = True
                else:
                    playerOneSelectedExpansion = playerOnePreferredExpansionCCWDirection.pop(0)
                    if playerOneSelectedExpansion in possibleExpansionLocations:
                        playerOneExpansionLocations.append(playerOneSelectedExpansion)
                        possibleExpansionLocations.remove(playerOneSelectedExpansion)
                        ccwRoundPlayerOne = False
                    else:
                        raise Exception("There are no expansion locations left for player one even though there is still locations available!")
            # player two goes second
            if ccwRoundPlayerTwo:
                playerTwoSelectedExpansion = playerTwoPreferredExpansionCCWDirection.pop(0)
                if playerTwoSelectedExpansion in possibleExpansionLocations:
                    playerTwoExpansionLocations.append(playerTwoSelectedExpansion)
                    possibleExpansionLocations.remove(playerTwoSelectedExpansion)
                    ccwRoundPlayerTwo = False
                else:
                    playerTwoSelectedExpansion = playerTwoPreferredExpansionCWDirection.pop(0)
                    if playerTwoSelectedExpansion in possibleExpansionLocations:
                        playerTwoExpansionLocations.append(playerTwoSelectedExpansion)
                        possibleExpansionLocations.remove(playerTwoSelectedExpansion)
                        ccwRoundPlayerTwo = True
                    else:
                        raise Exception("There are no expansion locations left for player one even though there is still locations available!")
            else:
                playerTwoSelectedExpansion = playerTwoPreferredExpansionCWDirection.pop(0)
                if playerTwoSelectedExpansion in possibleExpansionLocations:
                    playerTwoExpansionLocations.append(playerTwoSelectedExpansion)
                    possibleExpansionLocations.remove(playerTwoSelectedExpansion)
                    ccwRoundPlayerTwo = False
                else:
                    playerTwoSelectedExpansion = playerTwoPreferredExpansionCCWDirection.pop(0)
                    if playerTwoSelectedExpansion in possibleExpansionLocations:
                        playerTwoExpansionLocations.append(playerTwoSelectedExpansion)
                        possibleExpansionLocations.remove(playerTwoSelectedExpansion)
                        ccwRoundPlayerTwo = True
                    else:
                        raise Exception("There are no expansion locations left for player one even though there is still locations available!")

        
        
        

        if self.player == Player.PLAYER_ONE:
            self.expansionLocations = playerOneExpansionLocations
            logger.info("Player one expansion locations: " + str(playerOneExpansionLocations))
        else: 
            self.expansionLocations = playerTwoExpansionLocations  
            logger.info("Player two expansion locations: " + str(playerTwoExpansionLocations))      

        return

    async def on_step(self, iteration: int):
        if not self.expansionLocationsComputed:
            if self.player == Player.PLAYER_ONE:
                if BuildListProcessBot.PLAYER_TWO_START_LOCATION != StartLocation.UNKNOWN:
                    self.computeExpansionLocations()
                    self.expansionLocationsComputed = True
            else:
                if BuildListProcessBot.PLAYER_ONE_START_LOCATION != StartLocation.UNKNOWN:
                    self.computeExpansionLocations()
                    self.expansionLocationsComputed = True
        
        # always begin with checking and possibly advancing the buildlist
        self.checkAndAdvance()

        if not self.done:

            # next preconditions of the current task are checked
            ok = self.checkPreconditions()
            if ok:
                #built by worker or trained in building?
                if self.builtByWorker(self.currentTask):

                    if self.currentTask == UnitTypeId.REFINERY: 
                        result = self.buildRefinery()
                        if result:
                            self.finishedCurrentTask()
                        else:
                            raise Exception("Could not build gas building because there was no build location found!")
                    elif self.currentTask == UnitTypeId.COMMANDCENTER:
                        self.buildBase()
                    else:
                        gridPosition: Point2 = self.getNextBuildPositionAndAdvance(self.currentTask)

                        buildLocation: Point2 = self.convertGridPositionToCenter(self.currentTask,  gridPosition)

                        worker: Unit = self.getWorker(buildLocation)

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

            self.myWorkerDistribution()
        else:
            logger.info("Done with build list!")
            
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

        logger.info("Start location: " + str(self.startLocation) + str(self.game_info.player_start_location))
        logger.info("Grid start: " + str(self.gridStart))

        if self.player == Player.PLAYER_ONE:
            BuildListProcessBot.PLAYER_ONE_START_LOCATION = self.startLocation
        else: 
            BuildListProcessBot.PLAYER_TWO_START_LOCATION = self.startLocation

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



        
            
        
        






# TODO: special build locations for base
# TODO: turn if in unitToId to dict lookup





# starting the bot
# one enemy just for first testing
buildListInput = ["CommandCenter", "CommandCenter", "CommandCenter", "CommandCenter", "CommandCenter", "CommandCenter", "CommandCenter", "CommandCenter"]

run_game(maps.get("Flat128"), [
    Bot(Race.Terran, BuildListProcessBot(buildListInput.copy(), Player.PLAYER_ONE), name="PlayerOne"),
    Bot(Race.Terran, BuildListProcessBot(buildListInput.copy(), Player.PLAYER_TWO), name="PlayerTwo")
], realtime=True)