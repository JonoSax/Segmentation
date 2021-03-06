'''
this script is performing and measuring the ANHIR registerations
'''


# from HelperFunctions.SP_FeatureFinder import feature
from HelperFunctions.Utilities import dirMaker, getMatchingList, denseMatrixViewer, nameFromPath, drawLine
from HelperFunctions import *
# from nonRigidAlign import nonRigidAlign, nonRigidDeform
# from HelperFunctions.SP_AlignSamples import aligner
import numpy as np
import cv2
from glob import glob
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.cluster import KMeans
import scipy
import os

def annotateImages(dataHome, size, res):
    '''
    This adds the annotations to the images
    '''

    imgsrc = dataHome + str(size) + "/images/"
    annosrc = dataHome + "landmark/"

    imgs = sorted(glob(imgsrc + "*png*"))
    annos = sorted(glob(annosrc + "*"))

    annosToUse, imgsToUse = getMatchingList(annos, imgs, True)

    for a, i in zip(annosToUse, imgsToUse):
        img = cv2.imread(i)
        anno = pd.read_csv(a)
        for n in anno.index:
            k = n*5+3       # (255/5)^2 combinations == 2500
            pos = (np.array(anno.loc[n])[1:] * res).astype(int)
            cv2.circle(img, tuple(pos), 3, [0, k%255, int(k/50)], 8)

        # overwrite the original with the modified
        cv2.imwrite(i, img)

def getTransformedFeatures(dataHome, size, imgsrc):

    '''
    This extracts the annotated features from the annotated
    images 
    '''
    print("----- " + imgsrc + " -----")
    imgsrc = dataHome + str(size) + "/" + imgsrc + "/"
    annosrc = dataHome + "landmark/"

    annos = sorted(glob(annosrc + "S*"))

    imgs = sorted(glob(imgsrc + "*png*"))
    imgsToUse = getMatchingList(annos, imgs)

    greenPosAll = {}
    greenPosNo = []

    for i, a in zip(imgsToUse, annos):
        name = nameFromPath(i, 3)
        img = cv2.imread(i)

        # get the positions of the features (red channel always 0, green channel never 0)
        mask = (img[:, :, 0] == 0)*1 * (img[:, :, 1] != 0)*1
        maskPos = np.where(mask == 1)        
        gp = np.c_[maskPos[0], maskPos[1]]

        if len(gp) == 0:
            continue

        featsNo = len(pd.read_csv(a))

        # NOTE hardcoded because there is one feature which was removed from the 
        # sample during the specimenID and it's way to hard to compensate for that
        if name.find("7") > -1:
            featsNo -= 1

        greenPosNo.append(featsNo)

        greenPosAll[name] = gp

    return(greenPosAll, greenPosNo)

def getFeatureError(dataHome, size, imgSrc, plot = True):

    featurePos, featureNo = getTransformedFeatures(dataHome, size, imgSrc)

    imgdir = dataHome + str(size) + "/" + imgSrc + "/"
    imgs = sorted(glob(imgdir + "*png*"))

    annosImgs = getMatchingList(list(featurePos.keys()), imgs)

    keys = list(featurePos.keys())
    names = []
    featureErrors = []

    for refImg, tarImg, refP, tarP, refNo, tarNo in zip(annosImgs[:-1], annosImgs[1:], keys[:-1], keys[1:], featureNo[:-1], featureNo[1:]):
        name = tarP + "_" + imgSrc
        print(name)
        names.append(name)

        refFeatures = featurePos[refP]
        tarFeatures = featurePos[tarP]

        ref = cv2.imread(refImg)
        tar = cv2.imread(tarImg)

        # get the positions of the features
        # ref[np.where(np.sum(ref * np.array([-1, 1, -1]), axis = 2) > 0)]

        # get the point of the feature
        refPoint = KMeans(refNo).fit(refFeatures).cluster_centers_
        tarPoint = KMeans(tarNo).fit(tarFeatures).cluster_centers_

        vrS = []
        trS = []
        refImgc = ref.copy()
        tarImgc = tar.copy()
        for r, t in zip(refPoint, tarPoint):
            vr = ref[tuple(r.astype(int))].astype(int)
            tr = tar[tuple(t.astype(int))].astype(int)

            cv2.circle(refImgc, tuple(np.flip(r).astype(int)), 5, [255, 0, 0], 3)
            cv2.circle(tarImgc, tuple(np.flip(t).astype(int)), 5, [255, 0, 0], 3)
            
            vrS.append(vr)
            trS.append(tr)

        #cv2.imshow("test", np.hstack([refImgc, tarImgc])); cv2.waitKey(0)
        
        # sort one axis to assist in matching
        # refPoint = refPoint[np.argsort(np.array(vrS)[:, 1])]
        # tarPoint = tarPoint[np.argsort(np.array(trS)[:, 1])]

        refMatchStore = []
        tarMatchStore = []
        
        # Use the relative distance of points to infer which ones are matches
        for n, tr in enumerate(trS):
            # find the feature match with the smallest distance
            error = np.sum((tr-vrS)**2, axis = 1)
            pos = np.argmin(error)

            # if the error is larger than 0 then we have not got a match
            if np.min(error) > 0: 
                continue

            if np.sum((refPoint[pos] - tarPoint[n])**2) > np.inf and imgSrc != "maskedSamples":
                continue

            # create the target feature and its position in the list matches
            # the feature in the reference list
            refMatchStore.append(refPoint[pos])
            tarMatchStore.append(tarPoint[n])

            # remove the entry that was identified
            vrS = np.delete(vrS, pos, 0)
            refPoint = np.delete(refPoint, pos, 0)

        if plot:
            # matrix, shift = denseMatrixViewer([refMatchStore, tarMatchStore], plot = False)
            if refImgc.shape != tarImgc.shape:
                shapes = []
                shapes.append(refImgc.shape)
                shapes.append(tarImgc.shape)
                maxShape = np.max(np.array(shapes), axis = 0)
                plate = np.zeros(maxShape).astype(np.uint8)
                s = refImgc.shape; plate[:s[0], :s[1], :] = refImgc; refImgc = plate
                plate = np.zeros(maxShape).astype(np.uint8)
                s = tarImgc.shape; plate[:s[0], :s[1], :] = tarImgc; tarImgc = plate

            combImg = np.hstack([refImgc, tarImgc])
            for r, t in zip(refMatchStore, tarMatchStore):
                combImg = drawLine(combImg, np.flip(r), np.flip(t) + [refImgc.shape[1], 0], blur = 4)
                # matrix = drawLine(matrix, t-shift, r-shift)

            plt.imshow(combImg); plt.show()

            # plt.imshow(matrix); plt.show()

        # calculate the distance between the features
        error=np.sqrt(np.sum((np.array(refMatchStore) - np.array(tarMatchStore))**2, axis = 1))

        featureErrors.append(error)

    # convert into a dataframe
    errordf = pd.DataFrame(featureErrors).T
    errordf.columns = names

    return(errordf)

def processErrors(dataHome, size, datasrc, plot):

    '''
    Get the per feature error as a csv, save it and provide some quick stats
    '''

    annosrc = dataHome + "landmark/"

    names = nameFromPath(sorted(glob(annosrc + "S*")))

    # get the features and calculate the error between them
    featureErrors = getFeatureError(dataHome, size, datasrc, plot)

    # save as a csv
    dirMaker(dataHome + "landmark/")
    featureErrors.to_csv(dataHome + "landmark/" + datasrc + ".csv")

def quickStats(dfPath): 

    # read in the df
    df = pd.read_csv(dfPath, index_col=0)
    name = nameFromPath(dfPath)
    print("\n---- " + name + " ----")
    # Provide some quick stats
    names = list(df.keys())

    # NOTE to compare to ANHIR data, compute the 
    # landmark registration accuracy (TRE) which is:
    '''
    relative Target Registration Error (rTRE) as the 
    Euclidean distance between the submitted coordinates 
    xˆlj and the manually determined (ground truth) 
    coordinates xlj (withheld from participants)

    NOTE use the original image diagonal rather than the registered
    image diagonal.... 

    (Borovec, J., Kybic, J., Arganda-Carreras, I., Sorokin, D. V., 
    Bueno, G., Khvostikov, A. V., ... & Muñoz-Barrutia, A. (2020). 
    ANHIR: automatic non-rigid histological image registration 
    challenge. IEEE transactions on medical imaging, 39(10), 3042-3052.)
    '''

    tre = 3120
    # based on an image WxH or ~1700X2500 pixels

    for e, name in zip(df.T.values, names):
        # remove nans
        e = e[~np.isnan(e)]

        dist = np.round(np.median(e), 1)
        std = np.round(np.sqrt(np.std(e)), 1)
        qrt = np.round(scipy.stats.iqr(e),1)
        m = np.round(np.max(e), 2)
    
        print(name + ": " + str(dist) + "±" + str(qrt) + ", max=" + str(m))

    return(df)

def featureErrorAnalyser(dataHome, plot = False):

    # this is the hard coded order of the processing (ie image processing goes from
    # masked to aligned, then aligned to re...)
    processOrder = ["maskedSamples", "alignedSamples", "ReAlignedSamples", "NLalignedSamples"]

    dataSrc = dataHome + "landmark/"
    dfPath = glob(dataSrc + "*Samples.csv")
    dfs = []
    for p in processOrder:
        pathNo = np.where([d.find(p)>-1 for d in dfPath])[0][0]
        dfs.append(dfPath[pathNo])

    infoAll = []
    for d in dfs:
        infodf = quickStats(d)
        infoAll.append(np.sqrt(infodf))

    df = pd.concat(infoAll)

    names = sorted(nameFromPath(list(df.keys()), 4))
    ids = np.unique(nameFromPath(names, 2))

    print("---- pValues ----")
    for i in ids:
        keyInfo, _ = getMatchingList(list(df.keys()), [i], True)
        # print(keyInfo)
        for p0, p1 in zip(keyInfo[:-1], keyInfo[1:]):
            p0df = df[p0]
            p1df = df[p1]

            pV = scipy.stats.ttest_ind(p0df, p1df, nan_policy = 'omit').pvalue
            print(i + ": " + p0.split("_")[-1] + "-->" + p1.split("_")[-1] + " = " + str(pV))

    # plot the distribution of the errors
    # initialise
    info = []
    idstore = None

    if plot:
        for n in names:
            name = n.split("_")[-1]
            id = nameFromPath(n)
            if idstore is None or id == idstore:
                info.append(df[n])
                names.append(name)
            else:
                plt.hist(info)
                plt.legend(names)
                plt.title(idstore)
                plt.show()
                info = []; info.append(df[n])
                names = []; names.append(id)
            idstore = id

        plt.hist(info)
        plt.legend(names)
        plt.title(id)
        plt.show()
            

if __name__ == "__main__":

    src = '/eresearch/uterine/jres129/anhir/TargetTesting/'
    src = '/Volumes/resabi201900003-uterine-vasculature-marsden135/anhir/TargetTesting/'
    src = '/Volumes/USB/ANHIR/TargetTesting/'
    specs = sorted(glob(src + "C*"))
    size = 2.5
    newsize = str(size) + "b"
    res = 0.2
    cpuNo = 1

    for s in specs[1:2]:

        print("--------- Processing " + s + " ---------")
        dataHome = s + "/"
        print(dataHome)

        # transform the target images first 
        newsrc = s + "/" + str(newsize) + "/"

        newMaksed = newsrc + '/maskedSamples/'
        newInfo = newsrc + '/info/'
        newInfoNL = newsrc + '/infoNL/'
        newAligned = newsrc + '/alignedSamples/'
        newReAligned = newsrc + '/ReAlignedSamples/'
        newNLAligned = newsrc + "/NLAlignedSamples/"
        newFeatureSects = newsrc + "/FeatureSections/"
        '''
        downsize(dataHome, size, res, cpuNo)
        specID(dataHome, size, cpuNo)
        featFind(dataHome, size, cpuNo, featMin = 50, gridNo = 1, dist = 20)
        align(dataHome, size, cpuNo, errorThreshold=500)
        nonRigidAlign(dataHome, size, cpuNo, featsMin = 3, errorThreshold=500, selectCriteria="smooth", distFeats=10, featsMax=np.inf, extract = False, plot = False)
        
        # input("Hit any key to continue AFTER copying the found info into the new folder")
        copyinfo = ['images', 'info', 'infoNL', 'FeatureSections']
        for c in copyinfo:
            dirMaker(src + "/" + c)
            print("cp -r " + dataHome + str(size) + "/" + c + " " + newsrc)
            os.system("cp -r " + dataHome + str(size) + "/" + c + " " + newsrc)
            print("Copied " + c)
        
        
        # apply the feataures onto the images and deform them exactly the same as 
        # the target images
        
        annotateImages(dataHome, newsize, res)
        specID(dataHome, newsize, cpuNo, imgref = None)
        
        # linear alignment
        aligner(newMaksed, newInfo, newAligned, cpuNo, errorThreshold = 500)
        
        # alignment with the NL features
        aligner(newAligned, newInfoNL, newReAligned, cpuNo, errorThreshold = 500)

        # NL alignment
        dirMaker(newNLAligned, True)
        nonRigidDeform(newReAligned, \
            newNLAligned, \
                newFeatureSects, \
                    prefix = "png", flowThreshold = 100)
        
        reImgs = sorted(glob(newReAligned + "*.png"))
        NLImgs = sorted(glob(newNLAligned + "*.png"))
        for r, n in zip(reImgs, NLImgs):
            rName = nameFromPath(r, 3)
            prefix = n.split(".")[-1]
            os.rename(n, newNLAligned + "/" + rName + "." + prefix)
        '''
        # get the errors of the linear aligned features 
        # processErrors(dataHome, newsize, "maskedSamples", False)
        # processErrors(dataHome, newsize, "alignedSamples", False)
        processErrors(dataHome,  newsize, "ReAlignedSamples", False)
        # processErrors(dataHome, newsize, "NLAlignedSamples", False)
        # processErrors(dataHome, newsize, "LSE", False)

        featureErrorAnalyser(dataHome)

    '''
    # process all the statistics of the results gathered
    regomethods = ["_masked", "_aligned", "_NL"]

    # load the data
    specs = sorted(glob(src + "C*"))
    specNames = [s.split("/")[-1] for s in specs]
    data = []
    for s in specs:
        info = glob(s + "/*Samples.csv")
        specName = s.split("/")[-1]
        print(specName)
        for i in info:
            # read in the data frame
            df = pd.read_csv(i)
            df = df.drop("Unnamed: 0", axis = 1)
            # add the specimen name in the column
            df.columns = [str(col) + "_" + specName for col in df.columns]
            data.append(df.dropna().copy())

    alldf = pd.concat(data)
    alllist = [np.array(alldf[i].dropna()) for i in alldf]

    # create boxplots for every sample matched sample
    fig, ax = plt.subplots(3)
    reg = {}

    for n, r in enumerate(regomethods):
        regMeth = []
        for a in alldf:
            if a.find(r)>-1:
                regMeth.append(a)

        reg[r] = regMeth
        reglist = [np.array(alldf[i].dropna()) for i in regMeth]
        ax[n].boxplot(reglist)
        ax[n].set_title(r + " errors", size = 12)
        xtickNames = plt.setp(ax[n], xticklabels="")
        plt.setp(xtickNames, rotation=45, fontsize=8)
    fig.suptitle("Errors of registration methods", size = 24)
    fig.text(0.06, 0.5, 'Pixel error', ha='center', va='center', rotation='vertical', size = 20)
    samp = [nameFromPath(a.split("Samples_")[0]) for a in regMeth]
    spec = [a.split("Samples_")[1] for a in regMeth]
    samples = list(np.unique([sp + "_" + sa for (sa, sp) in zip(samp, spec)]))
    xtickNames = plt.setp(ax[-1], xticklabels=samples)
    plt.setp(xtickNames, rotation=45, fontsize=12)
    ax[1].set_ylim([0, 150])
    ax[2].set_ylim([0, 150])
    # plt.show()

    # get the distribution stats for each method
    for n, s in enumerate(samples):
        print("\n----- " + s + " -----")
        print(", med, IQR, pValue")
        info = {}
        for r in reg:
            info[r] = alldf[reg[r][n]].dropna()
            median = np.round(np.median(info[r]), 2)
            iqr = np.round(scipy.stats.iqr(info[r]), 2)

            print(", "+ str(median) + ", " + str(iqr))

        pV0 = scipy.stats.ttest_ind(info["_masked"], info["_aligned"], nan_policy = 'omit').pvalue
        pV1 = scipy.stats.ttest_ind(info["_aligned"], info["_NL"], nan_policy = 'omit').pvalue

        print("Masked vs Aligned: " + str(np.round(pV0, 2)))
        if pV1 > 0.05:
            print("!!! ", end="")
        print("Aligned vs NL: " + str(np.round(pV1, 2)))

        # print("Masked vs Aligned, " + str("{:.2e}".format(pV0)))
        # print("Aligned vs NL, " + str("{:.2e}".format(pV1)))

    
    infoStore = {}
    info = {}
    for r in regomethods:
        info[r] = []
        for a in alldf:
            if a.find(r)>-1:
                info[r].append(alldf[a])
        rInfo = pd.concat(info[r])
        infoStore[r] = np.array(rInfo)
        info[r] = rInfo.dropna()
        median = np.round(np.median(info[r]), 1)
        iqr = np.round(scipy.stats.iqr(info[r]),1)

        print(r + ": med = " + str(median) + " IQR = " + str(iqr))

    pV0 = scipy.stats.ttest_ind(info["_masked"], info["_aligned"], nan_policy = 'omit').pvalue
    pV1 = scipy.stats.ttest_ind(info["_aligned"], info["_NL"], nan_policy = 'omit').pvalue
    print("Masked vs Aligned: " + str("{:.2e}".format(pV0)))
    print("Aligned vs NL: " + str("{:.2e}".format(pV1)))
    regoMethod = pd.DataFrame.from_dict(infoStore)
    regoMethod.to_csv(src + "regoMethods.csv")
    # plt.boxplot([info["_masked"], info["_aligned"], info["_NL"]])

    # get the distribution stats for each method per specimen
    infoStore = {}
    for s in specNames:
        info = {}
        for r in regomethods:
            info[r] = []
            for a in alldf:
                if a.find(r)>-1 and a.find(s)>-1:
                    info[r].append(alldf[a])
            
            rInfo = pd.concat(info[r])
            infoStore[r] = np.array(rInfo)
            i = rInfo.dropna()
            median = np.round(np.median(i), 1)
            iqr = np.round(scipy.stats.iqr(i),1)

            print(s + " " + r + ": med = " + str(median) + " IQR = " + str(iqr))

        pV0 = scipy.stats.ttest_ind(infoStore["_masked"], infoStore["_aligned"], nan_policy = 'omit').pvalue
        pV1 = scipy.stats.ttest_ind(infoStore["_aligned"], infoStore["_NL"], nan_policy = 'omit').pvalue
        print("Masked vs Aligned: " + str("{:.2e}".format(pV0)))
        print("Aligned vs NL: " + str("{:.2e}".format(pV1)))
        specregoMethod = pd.DataFrame.from_dict(infoStore)
        specregoMethod.to_csv(src + s + "/regoMethods.csv")
        # plt.boxplot([info["aligned"], info["NL"]]); plt.show()

    '''    
