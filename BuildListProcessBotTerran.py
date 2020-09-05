from BuildListProcessBotBase import (
    BuildListProcessBotBase,
    Player,
    StartLocation,
    race_supplyUnit,
    raceBasicTownhall
)
import logging
import math
from sc2.data import race_worker
from sc2.data import race_townhalls
from sc2.position import Point2
from sc2.units import Units
from sc2.unit import Unit
from sc2.constants import (
    IS_STRUCTURE,
    ALL_GAS
)
from sc2.ids.unit_typeid import UnitTypeId
from sc2.game_data import UnitTypeData
from BuildListProcessorDicts import BASE_BUILDINGS
from sc2.dicts.unit_trained_from import UNIT_TRAINED_FROM

terranAddonBuildings = {UnitTypeId.BARRACKS, UnitTypeId.FACTORY, UnitTypeId.STARPORT}
terranFullAddonBuildings = {UnitTypeId.BARRACKSREACTOR, UnitTypeId.BARRACKSTECHLAB, UnitTypeId.FACTORYREACTOR, UnitTypeId.FACTORYTECHLAB, UnitTypeId.STARPORTREACTOR, UnitTypeId.STARPORTTECHLAB}


class BuildListProcessBotTerran(BuildListProcessBotBase):

    # Init
    # ----------------------------------------

    def __init__(self, inputBuildList, player: Player):
        # base class
        BuildListProcessBotBase.__init__(self, inputBuildList, player)
        self.gridStart: Point2 = Point2()
        
        self.loggerChild = logging.getLogger("BuildListProcessBotTerran" + self.playerString)

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

    # In theory not necessary because these could be replaced by methods from
    # from BuildListProcessBotBase but they are here because this is mostly
    # old code from times when no BuildListProcessBotBase existed.
    # ----------------------------------------

    def structureExists(self, structureType : UnitTypeId):
        return self.structures.filter(lambda unit: unit.is_structure).exists
         
    def producedInTownhall(self, unitId):
        if unitId in UNIT_TRAINED_FROM:
            producers = UNIT_TRAINED_FROM[unitId]
            return any(x in race_townhalls[self.race] for x in producers)
        else:
            return False

    def builtByWorker(self, unitId):
        if unitId in UNIT_TRAINED_FROM:
            producers = UNIT_TRAINED_FROM[unitId]
            return race_worker[self.race] in producers
        else:
            return False
    
    # Buildgrid
    # ----------------------------------------

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
    
        if unitId in terranAddonBuildings:
            if self.startLocation == StartLocation.BOTTOM_LEFT:
                result = result.offset((0.0, 2.0))
            elif self.startLocation == StartLocation.BOTTOM_RIGHT:
                result = result.offset((-2.0, 2.0))
            elif self.startLocation == StartLocation.TOP_RIGHT:
                result = result.offset((-2.0, 0.0))

        return result

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

    # Buidlist
    # ----------------------------------------   

    def raceSpecificUnitAndStructureCreations(self):
        pass

    def raceSpecificUnitCompletedIgnore(self, unit: UnitTypeId):
        return False

    def raceSpecificStructureCompletedIgnore(self, unit: UnitTypeId):
        # nothing to ignore
        return False

    # Running
    # ----------------------------------------

    async def on_step(self, iteration: int):
        # base does some more preparation -> only do something if base returns true
        if BuildListProcessBotBase.onStepBase(self, iteration):
            if iteration % 5 == 0:
                # do business here
                self.terranOnStep()
            pass

    def terranOnStep(self):
        # checking preconditions...
        # checks:
        #   - can afford (supply, minerals, vespene)
        #   - tech requirement
        #   - producer available
        ok: bool = self.checkPreconditions()
        # if necessarry more conditions can be checked next

        if ok:
            # if something is built by a worker we need to find a build position
            # this is handled in the then case of this if
            if self.builtByWorker(self.currentTask):

                # special cases: refinery and command centers:
                if self.currentTask == UnitTypeId.REFINERY: 
                    result = self.buildGasBuilding()
                    if result:
                        self.finishedCurrentTask()
                    else:
                        raise Exception("Could not build gas building because there was no build location found!")
                elif self.currentTask == UnitTypeId.COMMANDCENTER:
                    self.buildBase()
                    self.finishedCurrentTask()
                else:
                    # all other buildings are handled here
                    gridPosition: Point2 = self.getNextBuildPositionAndAdvance(self.currentTask)

                    buildLocation: Point2 = self.convertGridPositionToCenter(self.currentTask,  gridPosition)

                    worker: Unit = self.getWorker(buildLocation)

                    if self.can_place(self.currentTask, (buildLocation)):

                        worker.build(self.currentTask, buildLocation)

                        self.finishedCurrentTask()
                    else:
                        raise Exception("The provided build location is not valid!")

            else:
                
                # somehow need to find out if its training or building

                producers = self.getProducerIdsForCurrentTask()
                taskInfo: UnitTypeData = self.game_data.units[self.currentTask.value]

                # what to do next depends on whether the task is a structure or a unit
                if IS_STRUCTURE in taskInfo.attributes:
                    # the task is a structure but one that is not built by an scv

                    self.loggerChild.info(str(self.currentTask) + " is a structure!")
                    success = False
                    for structure in self.structures.idle:
                        if structure.type_id in producers:
                            self.loggerChild.info("found the structure that can built it")
                            success = structure.build(self.currentTask)
                            if success:
                                self.finishedCurrentTask()
                                break
                            else:
                                raise Exception("Could not cast the given ability!")
                    if not success:
                        raise Exception("Check preconditions reported that it could be cast but could not be cast!")
                else:
                    self.loggerChild.info(str(self.currentTask) + " is not a structure!")
                    if self.producedInTownhall(self.currentTask):
                        self.townhalls.idle[0].train(self.currentTask)
                        self.finishedCurrentTask()
                    else:
                        unitsTrained = self.train(self.currentTask)
                        if unitsTrained == 0:
                            self.loggerChild.info("could not train unit")
                        else:
                            self.finishedCurrentTask()

    # Startup Preparation
    # ----------------------------------------

    async def on_start(self):

        # call base to handle enemy location
        BuildListProcessBotBase.onStartBase(self)

        # left side of map
        if (self.startLocation == StartLocation.BOTTOM_LEFT):
            self.gridStart = self.game_info.player_start_location.offset((10, 10))
            self.colStop = self.gridStart.offset((0, 32))
        if (self.startLocation == StartLocation.TOP_LEFT):
            self.gridStart = self.game_info.player_start_location.offset((10, -10))
            self.colStop = self.gridStart.offset((0, -32))
        # right side of map
        if (self.startLocation == StartLocation.BOTTOM_RIGHT):
            self.gridStart = self.game_info.player_start_location.offset((-10, 10))
            self.colStop = self.gridStart.offset((0, 32))
        if (self.startLocation == StartLocation.TOP_RIGHT):
            self.gridStart = self.game_info.player_start_location.offset((-10, -10))
            self.colStop = self.gridStart.offset((0, -32))

        self.loggerChild.info("Grid start: " + str(self.gridStart))

        # fill self.plannedStructureSizes
        for buildTask in self.buildList:
            id = self.unitToId(buildTask)
            self.loggerChild.info("id:" + str(id) +  " name: "+ str(buildTask))
            if type(id) == UnitTypeId:
                unitTypeData: UnitTypeData = self.game_data.units[id.value]
                # if the building is a structure we store its footprint size
                if self.builtByWorker(id):
                    
                    # make sure it is not a gas bulilding and not a base building
                    if not id in ALL_GAS:
                        if not id in race_townhalls[self.race]:
                            radius = unitTypeData.footprint_radius
                            # in case this is a building that might have an addon
                            if id in terranAddonBuildings:
                                # increase radius by 1 to safe space for possible addons
                                radius += 1
                            self.loggerChild.info("Adding " + str(id) + " to structure sizes with radius " + str(radius))
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

       

        self.loggerChild.info("planned structure sizes:")
        self.loggerChild.info(str(self.plannedStructureSizes))

        # all the radiuses that need their own col
        radiuses = []
        for radius, count in self.plannedStructureSizes.items():
            # compute how many cols are necessary
            buildingsPerCol = self.maxColLength // (radius * 2) 
            colsNecessary = math.ceil(count / buildingsPerCol)

            self.numberOfCols += colsNecessary

            for i in range(0, colsNecessary):
                radiuses.append(radius)

        # iteration variables
        currentColStart = self.gridStart

        for radius in radiuses:

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


        self.loggerChild.info("Finished grid stuff!")
        self.loggerChild.info("Number of cols: " + str(self.numberOfCols))
        self.loggerChild.info("Cols widths: " + str(self.colsWidths))
        self.loggerChild.info("colsStarts: " + str(self.colsStarts))
        self.loggerChild.info("cols next build points: " + str(self.colsNextBuildPoint))

    # Attack
    # ----------------------------------------

    def attackMapCenterWithArmy(self):
        attackPoint = self.game_info.map_center
        army: Units = self.units.filter(lambda unit: not (unit.type_id == UnitTypeId.SCV))
        for unit in army:
            unit.attack(attackPoint)