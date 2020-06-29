import logging

from typing import Union, Dict

import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer
from sc2.units import Units
from sc2.unit import Unit
from sc2.dicts.unit_trained_from import UNIT_TRAINED_FROM
from sc2.game_data import AbilityData, GameData
from sc2.data import race_worker
from sc2.data import race_townhalls
from sc2.data import Race
from sc2.position import Point2, Point3
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId

logger = logging.getLogger(__name__)

race_supplyUnit: Dict[Race, UnitTypeId] = {
    Race.Protoss: UnitTypeId.NOTAUNIT,
    Race.Terran: UnitTypeId.SUPPLYDEPOT,
    Race.Zerg: UnitTypeId.NOTAUNIT,
}

class BuildListProcessBot(sc2.BotAI):

    def __init__(self, inputBuildList):
        self.buildList = inputBuildList
        self.currentTask = UnitTypeId.NOTAUNIT
        self.done = False

    def unitToId(self, unitName):
        if (unitName == "SupplyDepot"):
            return UnitTypeId.SUPPLYDEPOT
        if (unitName == "SCV"):
            return UnitTypeId.SCV
        if (unitName == "Barracks"):
            return UnitTypeId.BARRACKS
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
        for structure in self.structures:
            if structure._proto.unit_type == structureType.value:
                return True
        return False
        
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
            
            for structure in structuresToSearch:
                # TODO: use ready() on structures to check if any of them are completed
                if structure.type_id in producers:
                    if (structure.build_progress == 1.0):
                        result = (True, True)
                        return result
                    else:
                        # not available right now but later
                        result = (False, True)   
                        # we do not return here because we might find an instance of that building which is constructed

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



    def checkPreconditions(self):
        # check if the producer exists or is under construction
        producerExists, canWaitProducer = self.checkIfProducerExists(self.currentTask)
        if not producerExists and not canWaitProducer:
            raise Exception("There must be a producer for " + str(self.currentTask))
        # check if we can afford the unit/structure
        resourcesExist, canWaitResources = self.checkCosts(self.currentTask) 
        if not resourcesExist and not canWaitResources:
            raise Exception("There are no SCVs left who are able to harvest resources to afford " + str(self.currentTask))
        # check if tech requirement is fullfilled
        if self.tech_requirement_progress(self.currentTask) == 0:
            raise Exception("The tech requirement for " + str(self.currentTask) + " is not fullfilled!")

        # TODO: check if producer is idle/has free slots in queue

        # just return if we are able to build immediately --> if not that means we have to wait
        return producerExists and resourcesExist


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
                        location: Point2 = await self.find_placement(self.currentTask, worker.position, max_distance = 100, placement_step=3)
                        if location:
                            # Order worker to build exactly on that location
                            worker.build(self.currentTask, location)
                            self.finishedCurrentTask()
                else:
                    if self.producedInTownhall(self.currentTask):
                        self.townhalls.idle[0].train(self.currentTask)
                        self.finishedCurrentTask()
                    else:
                        logger.info("not implemented")












# starting the bot
# one enemy just for first testing
buildListInput = ["SCV", "Barracks", "SupplyDepot"]

run_game(maps.get("Flat128"), [
    Bot(Race.Terran, BuildListProcessBot(buildListInput)),
    Computer(Race.Protoss, Difficulty.Medium)
], realtime=True)