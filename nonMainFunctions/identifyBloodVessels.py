'''

This script specifically work for processing the samples when there are maunal
annotations.

Processing includes:
    - Extracting the sample from the ndpi file at the given zoom
    - Extracting any hand annotated drawings of the vessels and locations
    identified for alignment
    - Aligning the tissue
    - Extracting any particular features as defined by segSection

'''

from HelperFunctions import *

# dataHome is where all the directories created for information are stored 
dataTrain = '/Volumes/USB/H653A_11.3/'

# dataTrain = '/Users/jonathanreshef/Documents/2020/Masters/TestingStuff/Segmentation/Data.nosync/HistologicalTraining2/'

# research drive access from HPC
# dataTrain = '/eresearch/uterine/jres129/AllmaterialforBoydpaper/ResultsBoydpaper/ArcuatesandRadials/NDPIsegmentations/'

# research drive access via VPN
# dataTrain = '/Volumes/resabi201900003-uterine-vasculature-marsden135/All material for Boyd paper/Results Boyd paper/Arcuates and Radials/NDPI segmentations/'


size = 2.5
cpuNo = 5

if __name__ == "__main__":

    print("\n----------- SegLoad -----------")
    # extract the manual annotations
    SegLoad(dataTrain, cpuNo)

    print("\n----------- WSILoad -----------")
    # extract the tif file of the specified size
    WSILoad(dataTrain, size, cpuNo)

    print("\n----------- maskMaker -----------")
    # from the manually annotated blood vessels, make them into masks
    maskMaker(dataTrain, size, cpuNo)

    print("\n----------- WSIExtract -----------")
    # extract ONLY the blood vessels from the sample (masked)
    WSIExtract(dataTrain, size)
