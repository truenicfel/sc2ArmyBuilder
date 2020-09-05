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

from BuildListProcessorDicts import (
    BASE_BUILDINGS,
    CONVERT_TO_ID,
    StartLocation
)

import threading

# Definitions
# ----------------------------------------

race_supplyUnit: Dict[Race, UnitTypeId] = {
    Race.Protoss: UnitTypeId.PYLON,
    Race.Terran: UnitTypeId.SUPPLYDEPOT,
    Race.Zerg: UnitTypeId.OVERLORD,
}

raceBasicTownhall = {
    Race.Terran: UnitTypeId.COMMANDCENTER,
    Race.Zerg: UnitTypeId.HATCHERY,
    Race.Protoss: UnitTypeId.NEXUS
}

class Player(Enum):
    PLAYER_ONE = 1,
    PLAYER_TWO = 2,

class Winner(Enum):
    PLAYER_ONE = 1,
    PLAYER_TWO = 2,
    UNKNOWN = 3

# Class
# ----------------------------------------

class BuildListProcessBotBase(sc2.BotAI):

    # Constructor
    # ----------------------------------------

    def __init__(self, inputBuildList, player: Player):
        # player as string
        self.playerString = "UNKNOWN"
        if player == Player.PLAYER_ONE:
            self.playerString = "PlayerOne"
        else:
            self.playerString = "PlayerTwo"
        # logging
        self.loggerBase = logging.getLogger("BuildListProcessBotBase" + self.playerString)
        # player
        self.player: Player = player
        # start locations of both players
        BuildListProcessBotBase.PLAYER_ONE_START_LOCATION: StartLocation = StartLocation.UNKNOWN
        BuildListProcessBotBase.PLAYER_TWO_START_LOCATION: StartLocation = StartLocation.UNKNOWN
        # my start location
        self.startLocation: StartLocation = StartLocation.UNKNOWN
        # communication between bots
        # will be set when player one has set his start location
        BuildListProcessBotBase.PLAYER_ONE_START_LOCATION_EVENT: threading.Event = threading.Event()
        # will be set when player two has set his start location
        BuildListProcessBotBase.PLAYER_TWO_START_LOCATION_EVENT: threading.Event = threading.Event()
        # expansion locations (different datastructures for computing the expansion locations)
        self.expansionLocationsComputed = False
        self.bottomExpansions = list()
        self.topExpansions = list()
        self.leftExpansions = list()
        self.rightExpansions = list()
        BuildListProcessBotBase.PLAYER_ONE_EXPANSION_LOCATIONS = list()
        BuildListProcessBotBase.PLAYER_TWO_EXPANSION_LOCATIONS = list()
        self.expansionLocations = list()
        # build list
        self.buildList = inputBuildList
        self.currentTask = UnitTypeId.NOTAUNIT
        self.done = False
        self.remainingBuildTasks = dict()

        # gas building locations
        self.occupiedGeysers = set()

        # attacking
        self.attacking = False
        BuildListProcessBotBase.PLAYER_ONE_READY_TO_ATTACK = False
        BuildListProcessBotBase.PLAYER_TWO_READY_TO_ATTACK = False
        self.attackDone = False
        BuildListProcessBotBase.PLAYER_ONE_ARMY_COUNT = -1
        BuildListProcessBotBase.PLAYER_TWO_ARMY_COUNT = -1
        BuildListProcessBotBase.WINNER: Winner = Winner.UNKNOWN


    # Startup Preparation
    # ----------------------------------------
    
    def setSelfStartLocation(self):
        if (self.game_info.player_start_location.x == 24.5):
            # left side of map
            if (self.game_info.player_start_location.y == 22.5):
                self.startLocation = StartLocation.BOTTOM_LEFT
            else:
                self.startLocation = StartLocation.TOP_LEFT
        else:
            # right side of map
            if (self.game_info.player_start_location.y == 22.5):
                self.startLocation = StartLocation.BOTTOM_RIGHT
            else:
                self.startLocation = StartLocation.TOP_RIGHT
        
        self.loggerBase.info("Start location is " + str(self.startLocation))

        if self.player == Player.PLAYER_ONE:
            BuildListProcessBotBase.PLAYER_ONE_START_LOCATION = self.startLocation
        else:
            BuildListProcessBotBase.PLAYER_TWO_START_LOCATION = self.startLocation

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

        currentCCW: Point2 = self.getLocationFromStartLocation(BuildListProcessBotBase.PLAYER_ONE_START_LOCATION)
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

        currentCCW: Point2 = self.getLocationFromStartLocation(BuildListProcessBotBase.PLAYER_TWO_START_LOCATION)
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
        possibleExpansionLocations.remove(self.getLocationFromStartLocation(BuildListProcessBotBase.PLAYER_ONE_START_LOCATION))
        possibleExpansionLocations.remove(self.getLocationFromStartLocation(BuildListProcessBotBase.PLAYER_TWO_START_LOCATION))

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

        
        
        


        BuildListProcessBotBase.PLAYER_ONE_EXPANSION_LOCATIONS = playerOneExpansionLocations
        BuildListProcessBotBase.PLAYER_TWO_EXPANSION_LOCATIONS = playerTwoExpansionLocations   

        return

    def fillExpansionLocations(self):
        
        assert(BuildListProcessBotBase.PLAYER_TWO_START_LOCATION != StartLocation.UNKNOWN)
        assert(BuildListProcessBotBase.PLAYER_ONE_START_LOCATION != StartLocation.UNKNOWN)
        # compute expansions
        self.loggerBase.info("Computing expansion locations...")
        self.computeExpansionLocations()
        self.loggerBase.info("Player one expansion locations: " + str(BuildListProcessBotBase.PLAYER_ONE_EXPANSION_LOCATIONS))
        self.loggerBase.info("Player two expansion locations: " + str(BuildListProcessBotBase.PLAYER_TWO_EXPANSION_LOCATIONS))

    # startup routine. Should prepare:
    #   - enemy location
    # and scan the buildlist
    def onStartBase(self):
        self.setSelfStartLocation()
        self.loggerBase.info("Available start locations: " + str(self.game_info.start_locations))
        self.scanBuildList()
        self.prepareBuildListCompletedCheck()
    
    # BuildList
    # ----------------------------------------

    def checkAndAdvance(self):
        if not self.done:
            if self.currentTask == UnitTypeId.NOTAUNIT:
                if len(self.buildList) > 0:
                    # extract first build list element and set as current task
                    nextTaskName = self.buildList.pop(0)
                    self.currentTask = self.unitToId(nextTaskName)
                    self.loggerBase.info("Beginning next task: " + nextTaskName + "(" + str(self.currentTask) + ")")
                else:
                    self.done = True

    def finishedCurrentTask(self):
        self.loggerBase.info("Finished task: " + str(self.currentTask))
        self.currentTask = UnitTypeId.NOTAUNIT

    # preprocess of buildlist. checks:
    #   - number of expansions must be smaller or equal to seven
    #   - number of gas buildings must be smaller or equal to 2*(numberOfExpansions+1)
    #   - everything in buildlist is known to the bot
    def scanBuildList(self):

        buildListCopy = self.buildList.copy()

        expansionCount: int = 0
        gasBuildingCount: int = 0

        for element in buildListCopy:
            unitId: UnitTypeId = self.unitToId(element)

            if unitId == raceBasicTownhall[self.race]:
                expansionCount += 1
            elif unitId == race_gas[self.race]:
                gasBuildingCount += 1
        
        if expansionCount > 7:
            raise Exception("BuildList is invalid! To many expansions. Max: 7; Have: " + str(expansionCount))

        # add one to expansion count (natural)
        expansionCount += 1
        maxNumberOfGas: int = expansionCount * 2

        if gasBuildingCount > maxNumberOfGas:
            raise Exception("BuildList is invalid! To many gas buildings. Max:" + str(maxNumberOfGas) + "; Have: " + str(gasBuildingCount))

        self.loggerBase.info("BuildList has no errors.")

    def prepareBuildListCompletedCheck(self):
        self.remainingBuildTasks[race_worker[self.race]] = 12
        self.remainingBuildTasks[raceBasicTownhall[self.race]] = 1
        self.raceSpecificUnitAndStructureCreations()
        # add everything from build list
        for element in self.buildList:
            # convert to id
            unitId: UnitTypeId = self.unitToId(element)
            if unitId in self.remainingBuildTasks:
                self.remainingBuildTasks[unitId] += 1
            else:
                self.remainingBuildTasks[unitId] = 1
        self.loggerBase.info("Created remaining build tasks data structure: " + str(self.remainingBuildTasks))

    # this has to be implemented by a child class to avoid counting initial units 
    # (automatically given at the start of the game) as units that were created
    # use self.remainingBuildTasks to include them
    # an example for workers is given in self.prepareBuildListCompletedCheck()
    def raceSpecificUnitAndStructureCreations(self):
        raise Exception("Has to be implemented by race specific class!")

    async def on_building_construction_complete(self, unit: Unit):
        if not self.raceSpecificStructureCompletedIgnore(unit.type_id):
            self.loggerBase.info("Structure " + str(unit.type_id) + " completed!")
            self.remainingBuildTasks[unit.type_id] -= 1

    async def on_unit_created(self, unit: Unit):
        if not self.raceSpecificUnitCompletedIgnore(unit.type_id):
            self.loggerBase.info("Unit " + str(unit.type_id) + " completed!")
            self.remainingBuildTasks[unit.type_id] -= 1

    def raceSpecificStructureCompletedIgnore(self, unit: UnitTypeId):
        raise Exception("Has to be implemented by race specific bot!")

    def raceSpecificUnitCompletedIgnore(self, unit: UnitTypeId):
        raise Exception("Has to be implemented by race specific bot!")

    # this does not check if the list of build tasks is empty but it checks
    # if all buildings are ready and idle and if all remaining build tasks
    # have been completed
    def checkBuildListCompleted(self):
        
        if self.done:

            allStructuresReady = True
            allStructuresIdle = True

            for structure in self.structures:
                allStructuresReady = allStructuresReady and structure.is_ready
                if not structure.is_ready:
                    self.loggerBase.debug(str(structure) + " is not ready")
                allStructuresIdle = allStructuresIdle and structure.is_idle
                if not structure.is_idle:
                    self.loggerBase.debug(str(structure) + " is not idle")
        
            allUnitsReady = True
            for unit in self.units:
                allUnitsReady = allUnitsReady and unit.is_ready
                if not unit.is_ready:
                    self.loggerBase.debug(str(unit) + " is not ready!")
            
            if self.race == Race.Zerg:
                allUnitsReady = self.units.filter(lambda unit: unit.type_id == UnitTypeId.EGG).empty


            if not allStructuresReady:
                self.loggerBase.debug("Buildlist is done but not all structures are ready!")

            if not allStructuresIdle:
                self.loggerBase.debug("Buildlist is done but not all structures are idle!")

            if not allUnitsReady:
                self.loggerBase.debug("Buildlist is done but not all units are ready!")

            if allStructuresReady and allStructuresIdle and allUnitsReady:
                # the final check of remainingBuildTasks if everything was built
                for unitId, count in self.remainingBuildTasks.items():
                    # safety net for terran (and protoss)
                    if self.already_pending(unitId) > 0:
                        return False # the building is pending --> worker walking to build etc.
                    if unitId in BASE_BUILDINGS:
                        self.loggerBase.info("All units: \n" + str(self.all_units))
                    if count != 0:
                        if unitId == race_worker[self.race]:
                            self.loggerBase.warn("The bot did not produce the correct number of workers. Timings will not be correct but the army strength can still be compared!")
                        else:
                            if count > 0:
                                raise Exception("Everything should be done but " + str(unitId) + " was not build as many times as it was supposed to!")
                            else:
                                raise Exception("Everything should be done but " + str(unitId) + " was build more than it was supposed to!")
                return True
            else:
                return False


        else:
            return False
        
    # Units
    # ----------------------------------------
    
    def unitToId(self, unitName):
        if unitName not in CONVERT_TO_ID:
            raise Exception(unitName + " is not available in CONVERT_TO_ID!")
        return CONVERT_TO_ID[unitName]

    # returns the ids of producers for the current task
    def getProducerIdsForCurrentTask(self):
        if self.currentTask in UNIT_TRAINED_FROM:
            return UNIT_TRAINED_FROM[self.currentTask]
        elif self.currentTask in BASE_BUILDINGS:
            return BASE_BUILDINGS[self.currentTask]
        else:
            raise Exception("" + str(self.currentTask) + " is not available in UNIT_TRAINED_FROM and not in BASE_BUILDINGS (only terran)!")

    # returns actual units of producers for the current task
    def getProducerUnitsForCurrentTask(self):
        producerIds: Set[UnitTypeId] = self.getProducerIdsForCurrentTask()
        return (self.units + self.structures).filter(lambda unit: unit.type_id in producerIds)

    # returns true if the given unit id is a worker of the currently played race
    def isWorker(self, unitId: UnitTypeId):
        return race_worker[self.race] == unitId

    # Building/Training Conditions
    # ----------------------------------------

    def checkIfProducerExists(self):
        result = (False, False)
        producersAvailable: Units = self.getProducerUnitsForCurrentTask()
        producersAvailable = producersAvailable.ready
        if not producersAvailable.empty:
            # is any of these available producers idle
            if any(producer.is_idle or producer.is_gathering for producer in producersAvailable):
                result = (True, True)
            else:
                result = (False, True)
        else:
            # is any of the unit ids being produced or queued?
            producerIds = self.getProducerIdsForCurrentTask()
            if any(self.already_pending(producerId) > 0.0 for producerId in producerIds):
                result = (False, True)
            # for zerg producer might be larva. already_pending will not account for that
            # as long as we have a least one Hatchery/Lair/Hive
            if (not result[1]) and self.race == Race.Zerg and UnitTypeId.LARVA in producerIds and len(self.townhalls) > 0:
                result = (False, True)

        return result

    def checkCosts(self):
        cost = self.calculate_cost(self.currentTask)

        # TODO: the check here (self.workers.gathering > 0) does not work for terran and protoss

        minerals = (True, True)
        if cost.minerals > self.minerals:
            # not enough right now but maybe later?
            # at least some workers and
            if len(self.workers.gathering) > 0 and len(self.townhalls) > 0:
                minerals = (False, True)
            else:
                minerals = (False, False)
                self.loggerBase.warn("There are not enough minerals to build " + str(self.currentTask) + " and waiting does not help!")
        
        vespene = (True, True)
        if cost.vespene > self.vespene:
            # not enough right now but maybe later?
            if len(self.workers.gathering) > 0 and len(self.gas_buildings.ready) + self.already_pending(race_gas[self.race]):
                # waiting helps
                vespene = (False, True)
            else:
                vespene = (False, False)
                self.loggerBase.warn("There are not enough vespene to build " + str(self.currentTask) + " and waiting does not help!")

        supply = (True, True)
        supply_cost = self.calculate_supply_cost(self.currentTask)
        # make sure this thing actually has supply cost
        if isinstance(self.currentTask, UnitTypeId):
            if supply_cost and supply_cost > self.supply_left:
                # we dont have enough supply right now but maybe later?
                supply = (False, True)
                # check if supply building is being built
                # already pending checks everything: check its documentation
                if self.already_pending(race_supplyUnit[self.race]) == 0:
                    supply = (False, False)
                    self.loggerBase.warn("There is not enough supply to build " + str(self.currentTask) + " and waiting does not help!")

        return (minerals[0] and vespene[0] and supply[0], minerals[1] and vespene[1] and supply[1])

    def checkIfTechRequirementFulfilled(self):
        race_dict = {
            Race.Protoss: PROTOSS_TECH_REQUIREMENT,
            Race.Terran: TERRAN_TECH_REQUIREMENT,
            Race.Zerg: ZERG_TECH_REQUIREMENT,
        }
        # this gets the requirement for the unit we are checking
        requirement = race_dict[self.race][self.currentTask]
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
        producerExists, canWaitProducer = self.checkIfProducerExists()
        if not producerExists and not canWaitProducer:
            raise Exception("There must be a producer for " + str(self.currentTask))
        # check if we can afford the unit/structure
        resourcesExist, canWaitResources = self.checkCosts() 
        if not resourcesExist and not canWaitResources:
            raise Exception("There is not enough minerals, vespene or supply and waiting for it will not help!")
        # check if tech requirement is fullfilled only if the resources exist
        requirementFulfilled, canWaitRequirement = self.checkIfTechRequirementFulfilled()
        if not requirementFulfilled and not canWaitRequirement:
            raise Exception("The requirement for " + str(self.currentTask) + " is not fullfilled!")

        # just return if we are able to build immediately --> if not that means we have to wait
        return producerExists and resourcesExist and requirementFulfilled


        # finds an appropriate worker (closest to position or unit)
    
    # Building
    # ----------------------------------------
    def getWorker(self, position: Union[Unit, Point2, Point3]):
        workersGathering: Units = self.workers.gathering

        if workersGathering:
            # select worker closest to pos or unit
            return workersGathering.closest_to(position)
        else:
            raise Exception("There are no gathering workers which could be used to build " + self.currentTask)

    def buildGasBuildingAtTownhall(self, townhall: Unit):
        # all vespene geysers closer than distance ten to the current townhall
        vespeneGeysers: Units  = self.vespene_geyser.closer_than(10, townhall)
        self.loggerBase.info("Found " + str(len(vespeneGeysers)) + " vespene geyser locations!")
        # check all locations
        # TODO: apparently can_place does not work in this situation. it will say that a second refinery can be placed on the occupied geyser
        for vespeneGeyser in vespeneGeysers:
            if vespeneGeyser.position not in self.occupiedGeysers:
                if self.can_place(self.currentTask, (vespeneGeyser.position)):
                    worker: Unit = self.getWorker(vespeneGeyser)
                    worker.build_gas(vespeneGeyser)
                    self.occupiedGeysers.add(vespeneGeyser.position)
                    return True
                else:
                    self.loggerBase.warn("Can place stated not possible to place even though according to self.occupiedGeysers it should be free!")
        
        # if we reach this we have not found a building location
        return False

    def buildGasBuilding(self):
        # cant build more gas buildings than townhalls
        if len(self.gas_buildings.ready) + self.already_pending(self.currentTask) <= len(self.townhalls) * 2:
            
            # prefer townhalls that are ready
            for townhall in self.townhalls.ready:
                return self.buildGasBuildingAtTownhall(townhall)
            # townhalls that are not ready
            for townhall in self.townhalls.not_ready:
                return self.buildGasBuildingAtTownhall(townhall)

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

    # Worker Distribution
    # ----------------------------------------

    def myWorkerDistribution(self):

        # Shamelessly stolen from and modified: https://github.com/BurnySc2/python-sc2/blob/develop/examples/terran/mass_reaper.py
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
                        self.loggerBase.info("Moving one worker to harvest minerals at " + str(info["unit"]))
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
                    self.loggerBase.info("Moving one worker to harvest gas at " + str(info["unit"]))
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
                    self.loggerBase.info("Moving one worker to " + str(info["unit"]))
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
                        self.loggerBase.info("Moving one worker to harvest minerals at " + str(mineralField))
                        worker.gather(mineralField)

    # Attack
    # ----------------------------------------

    def attackMapCenterWithArmy(self):
        raise Exception("Must be implemented by race specific Bot!")

    # Run
    # ----------------------------------------

    # finishes preprocessing:
    #   - compute expansion locations
    def onStepBase(self, iteration: int):
        if not self.expansionLocationsComputed:
            # player one will compute for both
            if self.player == Player.PLAYER_ONE:
                if BuildListProcessBotBase.PLAYER_TWO_START_LOCATION != StartLocation.UNKNOWN:
                    self.fillExpansionLocations()
                    self.expansionLocationsComputed = True
                    self.loggerBase.info("Expansion locations computed at iteration: " + str(iteration))
                    self.expansionLocations = BuildListProcessBotBase.PLAYER_ONE_EXPANSION_LOCATIONS
            else:
                if BuildListProcessBotBase.PLAYER_TWO_EXPANSION_LOCATIONS:
                    self.loggerBase.info("Expansion locations available at iteration: " + str(iteration))
                    self.expansionLocations = BuildListProcessBotBase.PLAYER_TWO_EXPANSION_LOCATIONS
                    self.expansionLocationsComputed = True

        # it is important do to this b4 checking and advancing
        # because orders will be processed after one step is finished
        if (not self.attacking) and self.checkBuildListCompleted():
            self.loggerBase.info("All tasks in buildlist are finished and ready to fight!")
            if self.player == Player.PLAYER_ONE:
                BuildListProcessBotBase.PLAYER_ONE_READY_TO_ATTACK = True
            else:
                BuildListProcessBotBase.PLAYER_TWO_READY_TO_ATTACK = True
            self.attacking = True

        if BuildListProcessBotBase.PLAYER_TWO_READY_TO_ATTACK and BuildListProcessBotBase.PLAYER_TWO_READY_TO_ATTACK and not self.attackDone:
            self.loggerBase.info("Attacking the map center with all available units!")
            self.attackMapCenterWithArmy()
            self.attackDone = True

        if self.attackDone:
            if self.player == Player.PLAYER_ONE:
                BuildListProcessBotBase.PLAYER_ONE_ARMY_COUNT = self.army_count
            else:
                BuildListProcessBotBase.PLAYER_TWO_ARMY_COUNT = self.army_count
        
        if self.player == Player.PLAYER_ONE and (BuildListProcessBotBase.PLAYER_ONE_ARMY_COUNT == 0 or BuildListProcessBotBase.PLAYER_TWO_ARMY_COUNT == 0):
            if BuildListProcessBotBase.PLAYER_ONE_ARMY_COUNT == 0 and BuildListProcessBotBase.PLAYER_TWO_ARMY_COUNT == 0:
                self.loggerBase.info("Its a tie!")
            elif BuildListProcessBotBase.PLAYER_TWO_ARMY_COUNT == 0:
                self.loggerBase.info("Player two won the match!")
                BuildListProcessBotBase.WINNER = Winner.PLAYER_TWO
            else:
                self.loggerBase.info("Player one won the match!")
                BuildListProcessBotBase.WINNER = Winner.PLAYER_ONE

        if BuildListProcessBotBase.WINNER != Winner.UNKNOWN:
            if self.player == Player.PLAYER_ONE and BuildListProcessBotBase.WINNER == Winner.PLAYER_TWO:
                self.loggerBase.info("Player one should surrender now!")
            
            if self.player == Player.PLAYER_TWO and BuildListProcessBotBase.WINNER == Winner.PLAYER_ONE:
                self.loggerBase.info("Player two should surrender now!")
            

        
        self.checkAndAdvance()
        
        # distribute workers
        self.myWorkerDistribution()

        return self.expansionLocationsComputed and not self.done

        
