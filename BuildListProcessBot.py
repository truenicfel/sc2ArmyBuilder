import logging

import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer
from sc2.units import Units
from sc2.unit import Unit
from sc2.dicts.unit_trained_from import UNIT_TRAINED_FROM
from sc2.ids.ability_id import AbilityId
from sc2.game_data import AbilityData, GameData
from sc2.ids.unit_typeid import UnitTypeId

import UnitDatabase

logger = logging.getLogger(__name__)

class BuildListProcessBot(sc2.BotAI):

    def __init__(self, inputBuildList):
        self.buildList = inputBuildList
        self.currentTask = UnitTypeId.NOTAUNIT
        self.done = False
        self.unitDatabase = UnitDatabase.UnitDatabase("unit_db.csv")

    def unitToId(self, unitName):
        if (unitName == "SupplyDepot"):
            return UnitTypeId.SUPPLYDEPOT
        if (unitName == "SCV"):
            return UnitTypeId.SCV
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

    def checkIfProducerExists(self, unitIdToProduce):
        # result is a pair of two bools
        # first bool: states if the producer exists
        # second bool: states if we need to wait for it to be available
        result = (False, False)
        
        producers = UNIT_TRAINED_FROM[unitIdToProduce]
        logger.info("type of workers")
        # check if the thing is produced by a SCV
        if UnitTypeId.SCV in producers:
            # find workers
            workers: Units = self.workers.gathering
            if workers:
                result = (True, False)
            else:
                # are there any workers that are currently constructing stuff?
                workingWorkers = self.workers.filter(lambda unit: unit.is_constructing_scv)
                if workingWorkers:
                    result = (True, True)
        else:
            # the unit or structure is build by a structure (trained or transformed)
            # TODO: check if one of the prododucers exists (being built or built): it has to exist and needs a free slot in the build queue (one of them)
            for producer in producers:
                assert producer, f"structure_type can not be 0 or NOTAUNIT, but was: {producer}"
                logger.info(str(self._game_data.units))
                #creation_ability: AbilityData = self._game_data.units[producer].creation_ability
                #logger.info("creation ability of:" + str(unitIdToProduce))
                #logger.info(str(creation_ability))
                

        return result


    def checkPreconditions(self):
        producerExists, mustWait = self.checkIfProducerExists(self.currentTask)
        if not producerExists:
            logger.info("The producer does not exist!")
        if (producerExists and not mustWait):
            logger.info("The producer exists and is immediately available!")
        if (producerExists and mustWait):
            logger.info("The producer exists but is not immediately available!")


    async def on_step(self, iteration: int):
        if not self.done:
            # always begin with checking and possibly advancing the buildlist
            self.checkAndAdvance()

            # next preconditions of the current task are checked
            self.checkPreconditions()












# starting the bot
# one enemy just for first testing
buildListInput = ["SCV", "SupplyDepot"]

run_game(maps.get("Flat128"), [
    Bot(Race.Zerg, BuildListProcessBot(buildListInput)),
    Computer(Race.Protoss, Difficulty.Medium)
], realtime=True)