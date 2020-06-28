import logging

import sys
import numpy as np
import pandas

logger = logging.getLogger(__name__)

class UnitDatabase():

    def __init__(self, pathToCSV):
        self.data = pandas.read_csv(pathToCSV, header=0, na_values=[], sep=",")
        self.idName = "id"
        self.producerName = "producer"
        self.structureName = "structure"

    def getRowByUnitName(self, unitName):
        return self.data.loc[self.data[self.idName] == unitName]

    # Get list of producer names which produce unitName
    def getProducer(self, unitName):
        row = self.getRowByUnitName(unitName)
        producerString = row.iloc[0][self.producerName]
        return producerString.split("/")

    def isBuilding(self, unitName):
        row = self.getRowByUnitName(unitName)
        return row.iloc[0][self.structureName].astype(bool)
        
