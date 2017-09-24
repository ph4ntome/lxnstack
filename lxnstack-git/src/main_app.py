#lxnstack is a program to align and stack atronomical images
#Copyright (C) 2013-2014  Maurizio D'Addona <mauritiusdadd@gmail.com>

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import math
import time
import shutil
import subprocess
import webbrowser
import tempfile
from xml.dom import minidom
import paths
from PyQt4 import uic, Qt, QtCore, QtGui

def tr(s):
    return utils.tr(s)

import utils
import numpy as np
import scipy as sp
import cv2

def Int(val):
    i = math.floor(val)
    if ((val-i)<0.5):
        return int(i)
    else:
        return int(math.ceil(val))
    
def dist(x1,y1,x2,y2):
    return (((x2-x1)**2)+((y2-y1)**2))**0.5


class theApp(Qt.QObject):

    def __init__(self,lang='',args=[]):
        
        Qt.QObject.__init__(self)
        
        self._fully_loaded=False
        self.verbose=False
        
        self.parseArguments(args)

        self.resetLog('Starting lxnstack...')
        
        self._old_tab_idx=0
        self.__operating=False
        self.__updating_mwb_ctrls=False
        self._photo_time_clock=0
        self._ignore_histogrham_update = False #this will be used to avoid recursion loop!
        self._phase_align_data=None
        
        # it seems that kde's native dialogs work correctly while, on the contrary,
        # gnome's dialogs (and also dialogs of other desktop environmetns?) will not
        # display correclty! In this case the Qt (non native) dialogs will be
        # used.
        
        try:
            #try automatic detection
            if 'kde' == os.environ['XDG_CURRENT_DESKTOP'].lower():
                self._dialog_options = Qt.QFileDialog.Option(Qt.QFileDialog.HideNameFilterDetails)
            else:
                self._dialog_options = Qt.QFileDialog.Option(Qt.QFileDialog.HideNameFilterDetails | Qt.QFileDialog.DontUseNativeDialog)
        except Exception:
            # This should work in each Desktop Environment
            self._dialog_options = Qt.QFileDialog.Option(Qt.QFileDialog.HideNameFilterDetails | Qt.QFileDialog.DontUseNativeDialog)
        
        self.current_match_mode=cv2.TM_SQDIFF #TODO: Add selection box

        self.qapp=Qt.QApplication.instance() 
        
        self._generateOpenStrings()

        if not os.path.isdir(paths.TEMP_PATH):
            os.makedirs(paths.TEMP_PATH)
        
        if not os.path.isdir(paths.HOME_PATH):
            os.makedirs(paths.HOME_PATH)
            
        self.temp_path=paths.TEMP_PATH
                
        self.__current_lang=lang
        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom=1
        self.exposure=0
        self.zoom_enabled=False
        self.zoom_fit=False
        self.current_image = None
        self.ref_image=None
        self.current_dir='~'
        
        self.colors=[(QtCore.Qt.red,tr('red')),
                     (QtCore.Qt.green,tr('green')),
                     (QtCore.Qt.blue,tr('blue')),
                     (QtCore.Qt.yellow,tr('yellow')),
                     (QtCore.Qt.cyan,tr('cyan')),
                     (QtCore.Qt.magenta,tr('magenta')),
                     (QtCore.Qt.darkRed,tr('dark red')),
                     (QtCore.Qt.gray,tr('gray')),
                     (QtCore.Qt.darkYellow,tr('dark yellow')),
                     (QtCore.Qt.darkGreen,tr('dark green')),
                     (QtCore.Qt.darkCyan,tr('dark cyan')),
                     (QtCore.Qt.darkBlue,tr('dark blue')),
                     (QtCore.Qt.darkMagenta,tr('dark magenta')),
                     (QtCore.Qt.black,tr('black'))]
        
        self.component_table={}
        self.MWB_CORRECTION_FACTORS={}

        self.wasCanceled=False
        self.wasStopped=False
        self.wasStarted=False
        self.isPreviewing=False
        self.shooting=False
        
        self.current_align_method=0
        self.is_aligning=False
        
        self.showAlignPoints = True
        self.showStarPoints = True
        
        self.image_idx=-1
        self.ref_image_idx=-1
        self.dif_image_idx=-1
        self.point_idx=-1
        self.star_idx=-1

        self._bas=None
        self._drk=None
        self._stk=None
        self._flt=None
        self._hst=None
        
        self._preview_data=None
        self._preview_image=None
        
        self._old_stk=None
        self._oldhst=None
        
        self.autoalign_rectangle=(256,256)
        self.auto_align_use_whole_image=0
        
        self.manual_align=False

        self.ftype=np.float32

        self.wnd = uic.loadUi(os.path.join(paths.UI_PATH,'main.ui'))
        self.dlg = uic.loadUi(os.path.join(paths.UI_PATH,'option_dialog.ui'))
        self.about_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'about_dialog.ui'))
        self.save_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'save_dialog.ui'))
        self.stack_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'stack_dialog.ui'))
        self.align_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'align_dialog.ui'))
        self.levels_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'levels_dialog.ui'))
        self.video_dlg = uic.loadUi(os.path.join(paths.UI_PATH,'video_dialog.ui'))
        
        self.component_ctrl_table={}
        
        self.wnd.chartsTabWidget.setTabEnabled(1,False)
        self.wnd.chartsTabWidget.setTabEnabled(2,False)
        
        self.currentWidth=0
        self.currentHeight=0
        self.currentDepht=0
        
        self.use_colormap_jet = True

        self.result_w=0
        self.result_h=0
        self.result_d=3
        
        self.current_project_fname=None
        
        self.average_save_file='average'
        self.master_bias_save_file='master-bias'
        self.master_dark_save_file='master-dark'
        self.master_flat_save_file='master-flat'
        
        self.master_bias_file=None
        self.master_dark_file=None
        self.master_flat_file=None
        
        self.master_bias_mul_factor=1.0
        self.master_dark_mul_factor=1.0
        self.master_flat_mul_factor=1.0
                
        self.framelist=[]
        self.biasframelist=[]
        self.darkframelist=[]
        self.flatframelist=[]
        self.starslist=[]
        self.lightcurve={}
        
        self.tracking_align_point=False
        self.tracking_star_point=False
        self.use_cursor = QtCore.Qt.OpenHandCursor
        self.panning=False
        self.panning_startig=(0,0)
        self.panning_ending=(0,0)
        self.checked_seach_dark_flat=0
        self.checked_autodetect_rectangle_size=2
        self.checked_autodetect_min_quality=2
        self.checked_colormap_jet=2
        self.checked_custom_temp_dir=2
        self.custom_chkstate=0
        self.ftype_idx=0
        self.checked_compressed_temp=0
        self.custom_temp_path=os.path.join(paths.HOME_PATH,'.temp')
        self.checked_show_phase_img=2
        self.phase_interpolation_order=0
        self.interpolation_order=0
        self.use_image_time=True        
        
        self.progress_dialog = Qt.QProgressDialog()        
        self.progress_dialog.canceled.connect(self.canceled)
        
        self.frame_open_args={'rgb_fits_mode':True,
                              'convert_cr2':False,
                              'progress_bar':self.progress_dialog}
        
        self.fit_levels=False
        
        self.current_cap_device=cv2.VideoCapture(None)
        self.video_writer = cv2.VideoWriter()
        self.video_url=''
        self.writing=False
        self.captured_frames=0
        self.max_captured_frames=0
        self.current_cap_device_idx=-1
        self.save_image_dir=os.path.join(os.path.expandvars('$HOME'),'Pictures',paths.PROGRAM_NAME.lower())
        self.current_cap_combo_idx=-1
        self.devices=[]
        self.device_propetyes=None
        self.format=0
        self.fps=0
        self.resolution=0
        self.exposure_type=0
        self.exposure=0
        self.gain=0
        self.contrast=0
        self.brightness=0
        self.saturation=0
        self.hue=0
        self.max_points=10
        self.min_quality=0.20
        
        self.levelfunc_idx=0
        self.levels_range=[0,100]
        
        self.current_pixel=(0,0)
        
        self.statusLabelMousePos = Qt.QLabel()
        self.statusBar = self.wnd.statusBar()
        self.setUpStatusBar()
        self.imageLabel= Qt.QLabel()
        self.imageLabel.setMouseTracking(True)
        self.imageLabel.setAlignment(QtCore.Qt.AlignTop)
        self.wnd.imageViewer.setWidget(self.imageLabel)
        self.wnd.imageViewer.setAlignment(QtCore.Qt.AlignTop)
        
        self.viewHScrollBar =  self.wnd.imageViewer.horizontalScrollBar()
        self.viewVScrollBar =  self.wnd.imageViewer.verticalScrollBar()
        
        self.wnd.colorBar.current_val=None
        self.wnd.colorBar.max_val=1.0
        self.wnd.colorBar.min_val=0.0
        self.wnd.colorBar._is_rgb=False
        
        self.bw_colormap=None
        self.rgb_colormap=None
                
        self.wnd.manualAlignGroupBox.setEnabled(False)
        
        # resize callback
        self.wnd.__resizeEvent__= self.wnd.resizeEvent #base implementation
        self.wnd.resizeEvent = self.mainWindowResizeEvent #new callback
        
        # mousemove callback
        self.imageLabel.__mouseMoveEvent__= self.imageLabel.mouseMoveEvent #base implementation
        self.imageLabel.mouseMoveEvent = self.imageLabelMouseMoveEvent #new callback
        
        self.imageLabel.__mousePressEvent__ = self.imageLabel.mousePressEvent
        self.imageLabel.mousePressEvent = self.imageLabelMousePressEvent
        
        self.imageLabel.__mouseReleaseEvent__ = self.imageLabel.mouseReleaseEvent
        self.imageLabel.mouseReleaseEvent = self.imageLabelMouseReleaseEvent
        
        
        self.wnd.imageViewer.__wheelEvent__ = self.wnd.imageViewer.wheelEvent
        self.wnd.imageViewer.wheelEvent = self.imageViewerWheelEvent
        
        # paint callback
        self.imageLabel.__paintEvent__= self.imageLabel.paintEvent #base implementation
        self.imageLabel.paintEvent = self.imageLabelPaintEvent #new callback        
        
        # paint callback for colorBar
        self.wnd.colorBar.__paintEvent__= self.wnd.colorBar.paintEvent #base implementation
        self.wnd.colorBar.paintEvent = self.colorBarPaintEvent #new callback        

        # paint callback for histoGraphicsView
        self.levels_dlg.histoView.__paintEvent__= self.levels_dlg.histoView.paintEvent #base implementation
        self.levels_dlg.histoView.paintEvent = self.histoViewPaintEvent #new callback        

        # paint callback for ADU label
        self.wnd.aduLabel.__paintEvent__= self.wnd.aduLabel.paintEvent #base implementation
        self.wnd.aduLabel.paintEvent = self.aduLabelPaintEvent #new callback        

        # paint callback for Mag label
        self.wnd.magLabel.__paintEvent__= self.wnd.magLabel.paintEvent #base implementation
        self.wnd.magLabel.paintEvent = self.magLabelPaintEvent #new callback        


        # exit callback
        self.wnd.__closeEvent__= self.wnd.closeEvent #base implementation
        self.wnd.closeEvent = self.mainWindowCloseEvent #new callback
        
        # paint callback
        self.levels_dlg.previewLabel.__paintEvent__= self.levels_dlg.previewLabel.paintEvent #base implementation
        self.levels_dlg.previewLabel.paintEvent = self.previewLabelPaintEvent #new callback        

        self.wnd.alignGroupBox.setEnabled(False)
        self.wnd.manualAlignGroupBox.setEnabled(False)
        self.wnd.masterBiasGroupBox.setEnabled(False)
        self.wnd.masterDarkGroupBox.setEnabled(False)
        self.wnd.masterFlatGroupBox.setEnabled(False)
        self.wnd.masterBiasGroupBox.hide()
        self.wnd.masterDarkGroupBox.hide()
        self.wnd.masterFlatGroupBox.hide()
        self.wnd.stopCapturePushButton.hide()
        self.wnd.rawModeWidget.hide()
        self.wnd.captureWidget.hide()
        self.wnd.magDoubleSpinBox.setEnabled(False)
        self.changeAlignMethod(self.current_align_method)
        self.wnd.fitMinMaxCheckBox.setCheckState(0)
        
        self.save_dlg.radioButtonFits.setEnabled(utils.FITS_SUPPORT)
        
        self.wnd.zoomCheckBox.stateChanged.connect(self.setZoomMode)
        self.wnd.zoomSlider.valueChanged.connect(self.signalSliderZoom)
        self.wnd.zoomDoubleSpinBox.valueChanged.connect(self.signalSpinZoom)
        self.wnd.addPushButton.clicked.connect(self.doLoadFiles)
        self.wnd.remPushButton.clicked.connect(self.removeImage)
        self.wnd.clrPushButton.clicked.connect(self.clearList)
        self.wnd.biasAddPushButton.clicked.connect(self.doAddBiasFiles)
        self.wnd.biasClearPushButton.clicked.connect(self.doClearBiasList)
        self.wnd.darkAddPushButton.clicked.connect(self.doAddDarkFiles)
        self.wnd.darkClearPushButton.clicked.connect(self.doClearDarkList)
        self.wnd.flatAddPushButton.clicked.connect(self.doAddFlatFiles)
        self.wnd.flatClearPushButton.clicked.connect(self.doClearFlatList)
        self.wnd.listCheckAllBtn.clicked.connect(self.checkAllListItems)
        self.wnd.listUncheckAllBtn.clicked.connect(self.uncheckAllListItems)
        self.wnd.alignDeleteAllPushButton.clicked.connect(self.clearAlignPoinList)
        self.wnd.starsDeleteAllPushButton.clicked.connect(self.clearStarsList)
        self.wnd.listWidget.currentRowChanged.connect(self.listItemChanged)
        self.wnd.listWidgetManualAlign.currentRowChanged.connect(self.manualAlignListItemChanged)
        self.wnd.listWidgetManualAlign.itemChanged.connect(self.currentManualAlignListItemChanged)
        self.wnd.starsListWidget.itemChanged.connect(self.starsListItemChanged)
        self.wnd.alignPointsListWidget.currentRowChanged.connect(self.alignListItemChanged)
        self.wnd.starsListWidget.currentRowChanged.connect(self.currentStarsListItemChanged)
        self.wnd.avrPushButton.clicked.connect(self.doStack)
        self.wnd.saveVideoPushButton.clicked.connect(self.doSaveVideo)
        self.wnd.levelsPushButton.clicked.connect(self.editLevels)
        self.wnd.toolBox.currentChanged.connect(self.updateToolBox)
        self.wnd.spinBoxXAlign.valueChanged.connect(self.shiftX)
        self.wnd.spinBoxYAlign.valueChanged.connect(self.shiftY)
        self.wnd.spinBoxXStar.valueChanged.connect(self.shiftStarX)
        self.wnd.spinBoxYStar.valueChanged.connect(self.shiftStarY)
        self.wnd.innerRadiusDoubleSpinBox.valueChanged.connect(self.setInnerRadius)
        self.wnd.middleRadiusDoubleSpinBox.valueChanged.connect(self.setMiddleRadius)
        self.wnd.outerRadiusDoubleSpinBox.valueChanged.connect(self.setOuterRadius)
        self.wnd.magDoubleSpinBox.valueChanged.connect(self.setMagnitude)
        self.wnd.doubleSpinBoxOffsetX.valueChanged.connect(self.shiftOffsetX)
        self.wnd.doubleSpinBoxOffsetY.valueChanged.connect(self.shiftOffsetY)
        self.wnd.spinBoxOffsetT.valueChanged.connect(self.rotateOffsetT)
        self.wnd.addPointPushButton.clicked.connect(self.addAlignPoint)
        self.wnd.removePointPushButton.clicked.connect(self.removeAlignPoint)
        self.wnd.addStarPushButton.clicked.connect(self.addStar)
        self.wnd.removeStarPushButton.clicked.connect(self.removeStar)
        self.wnd.alignPushButton.clicked.connect(self.doAlign)
        self.wnd.saveResultPushButton.clicked.connect(self.saveResult)
        self.wnd.autoSetPushButton.clicked.connect(self.autoSetAlignPoint)
        self.wnd.autoDetectPushButton.clicked.connect(self.autoDetectAlignPoints)
        self.wnd.masterBiasCheckBox.stateChanged.connect(self.useMasterBias)
        self.wnd.masterDarkCheckBox.stateChanged.connect(self.useMasterDark)
        self.wnd.masterFlatCheckBox.stateChanged.connect(self.useMasterFlat)
        self.wnd.masterBiasPushButton.clicked.connect(self.loadMasterBias)
        self.wnd.masterDarkPushButton.clicked.connect(self.loadMasterDark)
        self.wnd.masterFlatPushButton.clicked.connect(self.loadMasterFlat)
        self.wnd.stopCapturePushButton.clicked.connect(self.stopped)
        self.wnd.capturePushButton.clicked.connect(self.started)
        self.wnd.singleShotPushButton.clicked.connect(self.oneShot)
        self.wnd.captureGroupBox.toggled.connect(self.capture)
        self.wnd.rawGroupBox.toggled.connect(self.updateBayerMatrix)
        self.wnd.bayerComboBox.currentIndexChanged.connect(self.updateBayerMatrix)
        self.wnd.biasMulDoubleSpinBox.valueChanged.connect(self.setBiasMul)
        self.wnd.darkMulDoubleSpinBox.valueChanged.connect(self.setDarkMul)
        self.wnd.flatMulDoubleSpinBox.valueChanged.connect(self.setFlatMul)
        self.wnd.alignMethodComboBox.currentIndexChanged.connect(self.changeAlignMethod)
        self.wnd.fitMinMaxCheckBox.stateChanged.connect(self.setDisplayLevelsFitMode)
        self.wnd.exportCVSPushButton.clicked.connect(self.exportNumericDataCSV)
        self.wnd.minLevelDoubleSpinBox.valueChanged.connect(self.setMinLevel)
        self.wnd.maxLevelDoubleSpinBox.valueChanged.connect(self.setMaxLevel)
        
        self.dlg.devComboBox.currentIndexChanged.connect(self.getDeviceInfo)
        self.dlg.videoSaveDirPushButton.clicked.connect(self._set_save_video_dir)
        self.dlg.formatComboBox.currentIndexChanged.connect(self.deviceFormatChanged)
        self.dlg.resolutionComboBox.currentIndexChanged.connect(self.deviceResolutionChanged)
        self.dlg.fpsComboBox.currentIndexChanged.connect(self.deviceFpsChanged)
        self.dlg.expTypeComboBox.currentIndexChanged.connect(self.deviceExposureTypeChanged)
        self.dlg.expSlider.valueChanged.connect(self.deviceExposureChanged)
        self.dlg.gainSlider.valueChanged.connect(self.deviceGainChanged)
        self.dlg.contrastSlider.valueChanged.connect(self.deviceContrastChanged)
        self.dlg.brightnessSlider.valueChanged.connect(self.deviceBrightnessChanged)
        self.dlg.saturationSlider.valueChanged.connect(self.deviceSaturationChanged)
        self.dlg.hueSlider.valueChanged.connect(self.deviceHueChanged)
        self.dlg.sharpSlider.valueChanged.connect(self.deviceSharpnessChanged)
        self.dlg.gammaSlider.valueChanged.connect(self.deviceGammaChanged)        
        self.dlg.jetCheckBox.stateChanged.connect(self.setJetmapMode)
        self.dlg.jetCheckBox.setCheckState(2)
        self.dlg.fTypeComboBox.currentIndexChanged.connect(self.setFloatPrecision)
        self.dlg.jetCheckBox.setCheckState(2)
        self.dlg.tempPathPushButton.clicked.connect(self._set_temp_path)
        self.dlg.phaseIntOrderSlider.valueChanged.connect(self.setPhaseInterpolationOrder)
        self.dlg.intOrderSlider.valueChanged.connect(self.setInterpolationOrder)
        self.dlg.showPhaseImgCheckBox.stateChanged.connect(self.setShowPhaseIamge)
        
        self.save_dlg.radioButtonJpeg.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonPng.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonTiff.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonFits.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonNumpy.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonInt.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButtonFloat.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButton8.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButton16.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButton32.toggled.connect(self.updateSaveOptions)
        self.save_dlg.radioButton64.toggled.connect(self.updateSaveOptions)
        self.save_dlg.checkBoxUnsigned.stateChanged.connect(self.updateSaveOptions)
        self.save_dlg.pushButtonDestDir.clicked.connect(self.getDestDir)
        
        self.levels_dlg.curveTypeComboBox.currentIndexChanged.connect(self.updateHistograhm)
        self.levels_dlg.aDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.bDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.oDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.nDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.mDoubleSpinBox.valueChanged.connect(self.updateHistograhm2)
        self.levels_dlg.dataClippingGroupBox.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.dataClipping8BitRadioButton.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.dataClippingFitDataRadioButton.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.MWBGroupBox.toggled.connect(self.updateHistograhm2)
        self.levels_dlg.histLogViewCheckBox.stateChanged.connect(self.updateHistograhm2)
        self.levels_dlg.buttonBox.clicked.connect(self.levelsDialogButtonBoxClickedEvent)
        self.levels_dlg.histoTabWidget.currentChanged.connect(self.updateHistograhm2)
        
        self.wnd.genADUPushButton.clicked.connect(self.deGenerateLightCurves)
        self.wnd.aduListWidget.currentRowChanged.connect(self.updateADUlistItemChanged)
        self.wnd.aduListWidget.itemChanged.connect(self.wnd.aduLabel.repaint)
        self.wnd.colorADUComboBox.currentIndexChanged.connect(self.setCurrentADUCurveColor)
        self.wnd.lineADUComboBox.currentIndexChanged.connect(self.setCurrentADUCurveLineType)
        self.wnd.pointsADUComboBox.currentIndexChanged.connect(self.setCurrentADUCurvePointsType)
        self.wnd.barsADUComboBox.currentIndexChanged.connect(self.setCurrentADUCurveBarsType)
        self.wnd.smoothingADUDoubleSpinBox.valueChanged.connect(self.setCurrentADUCurveSmooting)
        self.wnd.pointSizeADUDoubleSpinBox.valueChanged.connect(self.setCurrentADUPointSize)
        self.wnd.lineWidthADUDoubleSpinBox.valueChanged.connect(self.setCurrentADULineWidth)
        
        self.wnd.magListWidget.currentRowChanged.connect(self.updateMaglistItemChanged)
        self.wnd.magListWidget.itemChanged.connect(self.wnd.magLabel.repaint)
        self.wnd.colorMagComboBox.currentIndexChanged.connect(self.setCurrentMagCurveColor)
        self.wnd.lineMagComboBox.currentIndexChanged.connect(self.setCurrentMagCurveLineType)
        self.wnd.pointsMagComboBox.currentIndexChanged.connect(self.setCurrentMagCurvePointsType)
        self.wnd.barsMagComboBox.currentIndexChanged.connect(self.setCurrentMagCurveBarsType)
        self.wnd.smoothingMagDoubleSpinBox.valueChanged.connect(self.setCurrentMagCurveSmooting)
        self.wnd.pointSizeMagDoubleSpinBox.valueChanged.connect(self.setCurrentMagPointSize)
        self.wnd.lineWidthMagDoubleSpinBox.valueChanged.connect(self.setCurrentMagLineWidth)
        self.wnd.saveADUChartPushButton.clicked.connect(self.saveADUChart)
        self.wnd.saveMagChartPushButton.clicked.connect(self.saveMagChart)
        
        self.wnd.actionOpen_files.triggered.connect(self.doLoadFiles)
        self.wnd.actionNew_project.triggered.connect(self.doNewProject)
        self.wnd.actionSave_project_as.triggered.connect(self.doSaveProjectAs)
        self.wnd.actionSave_project.triggered.connect(self.doSaveProject)
        self.wnd.actionLoad_project.triggered.connect(self.doLoadProject)
        self.wnd.actionPreferences.triggered.connect(self.doSetPreferences)
        self.wnd.actionAbout.triggered.connect(self.doShowAbout)
        self.wnd.actionUserManual.triggered.connect(self.doShowUserMan)

        self._resetPreferencesDlg()
        
        self.setLevelsRange((0,100))
        self.setDisplayLevelsFitMode(0)
        
        self.updateChartColors()

        if not os.path.isdir(self.save_image_dir):
            os.makedirs(self.save_image_dir)
        
        if not os.path.isdir(self.custom_temp_path):
            os.makedirs(self.custom_temp_path)
            
        self.setZoomMode(1,True)
        
        self.newProject()
                
        self.trace('Program started')
    
    def setFullyLoaded(self):
        self._fully_loaded=True
    
    def fullyLoaded(self):
        return self._fully_loaded
    
    #TODO: switch to argparse module
    def parseArguments(self,args):
                
        lproject=[None,'']
        sproject=[None,'']
        stacking=[None,'']
        align=[None,[False,False,False]]
        images=[None,[]]
        light=False
        
        for arg in args:
            
            if arg[0]=='-':
                if (images[0]==False) and len(images[1])>0:
                    images[0]=True
                
                if (align[0]==False):
                    align=[True,[False,True,True]]
            
            if (arg=="--lightcurve"):
                light=True
            elif ('--align' in arg):
                if '=' in arg:
                    val=arg.split('=')[1]
                    if val=='align-derotate':
                        align[1]==[False,True,True]
                    elif val=='align-only':
                        align[1]==[False,True,False]
                    elif val=='derotate-only':
                        align[1]==[False,False,True]
                    elif val=='reset':
                        align[1]==[True,False,False]
                    else:
                        self.criticalError('\n\''+val+'\' is not a recognized mode for --align.\nPlease use --help for more informations\n',False)
                else:
                    align[0]=False
            elif (arg=='-a'):
                align[0]=False
            elif ('--load-project' in arg):
                if '=' in arg:
                    val=arg.split('=')[1]
                    if val!='':
                        lproject=[True,val]
                    else:
                        self.criticalError('\nNo file specified for --load-project=FILE.\nPlease use --help for more informations\n',False)
                else:
                    lproject[0]=False
            elif (arg=='-l'):
                lproject[0]=False
            elif ('--save-project' in arg):
                if '=' in arg:
                    val=arg.split('=')[1]
                    if val!='':
                        sproject=[True,val]
                    else:
                        self.criticalError('\nInvalid syntax for --save-project[=FILE].\nPlease use --help for more informations\n',False)
                else:
                    sproject[0]=False
            elif(arg=='-s'):
                sproject[0]=False
            elif ('--stack' in arg):
                if '=' in arg:
                    val=arg.split('=')[1]
                    if val=='average':
                        stacking=[True,0]
                    elif val=='median':
                        stacking=[True,1]
                    elif val=='sigma-clipping':
                        stacking=[True,2]
                    elif val=='stddev':
                        stacking=[True,3]
                    elif val=='variance':
                        stacking=[True,4]
                    elif val=='maximum':
                        stacking=[True,5]
                    elif val=='minimum':
                        stacking=[True,6]
                    elif val=='maximum':
                        stacking=[True,7]
                    else:
                        self.criticalError('\n\''+val+'\' is not a recognized mode for --align.\nPlease use --help for more informations\n',False)
                else:
                    stacking[0]=False
            elif (arg=='-S'):
                stacking[0]=False
            elif (arg=='--add-images') or (arg=='-i'):
                images[0]=False
            elif (arg=='--verbose'):
                self.verbose=True
            else:
                if arg[0]=='-':
                    self.criticalError('\n\''+arg+'\' is not a recognized command.\nPlease use --help for more informations\n',False)
                elif align[0]==False:
                    if arg=='align-derotate':
                        align[1]=[False,True,True]
                    elif arg=='align-only':
                        align[1]=[False,True,False]
                    elif arg=='derotate-only':
                        align[1]=[False,False,True]
                    elif arg=='reset':
                        align[1]=[True,False,False]
                    else:
                        align[1]=[False,True,True]
                    align[0]=True
                elif lproject[0]==False:
                    lproject[0]=True
                    lproject[1]=arg
                elif sproject[0]==False:
                    sproject[0]=True
                    sproject[1]=arg
                elif stacking[0]==False:
                    stacking[0]=True
                    if arg=='average':
                        stacking=[True,0]
                    elif arg=='median':
                        stacking=[True,1]
                    elif arg=='sigma-clipping':
                        stacking=[True,2]
                    elif arg=='stddev':
                        stacking=[True,3]
                    elif arg=='variance':
                        stacking=[True,4]
                    elif arg=='maximum':
                        stacking=[True,5]
                    elif arg=='minimum':
                        stacking=[True,6]
                    elif arg=='product':
                        stacking=[True,7]
                    else:
                        self.criticalError('\n\''+val+'\' is not a recognized mode for --stack.\nPlease use --help for more informations\n',False)
                elif images[0]==False:
                    images[1].append(arg)
                else:
                    lproject[0]=True
                    lproject[1]=arg
                    
        if (images[0]==False) and len(images[1])>0:
            images[0]=True
        
        #default values
        if sproject[0]==False:
            if lproject[0]==True:
                sproject=[True,lproject[1]]
            else:
                self.criticalError('No project name specified!\nPlease use --help for more informations\n',False)
         
        if align[0]==False:
            align=[True,[False,True,True]]
         
        if stacking[0]==False:
            stacking=[True,0]
        
        self.args=(lproject,images,align,sproject,stacking,light)
        
    def executeCommads(self):
        if self.args[0][0]==True:
            self.loadProject(self.args[0][1])
        if self.args[1][0]==True:
            self.loadFiles(self.args[1][1])
        if self.args[2][0]==True:
            self.wnd.toolBox.setCurrentIndex(1)
            self.align(self.args[2][1][0], self.args[2][1][1], self.args[2][1][2])
        if self.args[3][0]==True:
            self.current_project_fname=self.args[3][1]
            self._save_project()
        if self.args[4][0]==True:
            self.wnd.toolBox.setCurrentIndex(7)
            self.stack(self.args[4][1])
        if self.args[5]==True:
            self.wnd.toolBox.setCurrentIndex(6)
            self.generateLightCurves(0)
        
        self.setFullyLoaded()
    
    def criticalError(self,msg,msgbox=True):
        utils.trace(msg,verbose=True)
        if msgbox:
            utils.showErrorMsgBox(msg)
        sys.exit(1)
        
    def resetLog(self,msg):
        utils.trace(msg,reset=True,verbose=self.verbose)
        
    def trace(self,msg):
        utils.trace(msg,verbose=self.verbose)
    
    def clearResult(self):
        
        del self._stk
        del self._drk
        del self._flt
        del self._old_stk
        del self._oldhst
        del self._hst
        del self._preview_data
        
        self._stk=None
        self._bas=None
        self._drk=None
        self._flt=None
        self._old_stk=None        
        self._oldhst=None
        self._hst=None
        self._preview_data=None
        self._preview_image=None
        
        self.updateResultImage()
    
    def activateResultControls(self):
        self.wnd.saveResultPushButton.setEnabled(True)
        self.wnd.levelsPushButton.setEnabled(True)
        
    def deactivateResultControls(self):
        self.wnd.saveResultPushButton.setEnabled(False)
        self.wnd.levelsPushButton.setEnabled(False)
    
    def updateBayerComponents(self):
        if self.currentDepht == 'L':
            if self.isBayerUsed():
                self.addComponents(('R','G','B'))
            else:
                self.addComponents(('L',))
        else:
            self.addComponents(list(self.currentDepht))
        
    def getNumberOfComponents(self):
        return len(self.component_table)
    
    def getComponentName(self,index):
        return self.component_table[index]
    
    def clearComponents(self):
        for i in range(self.getNumberOfComponents()):
            self.removeComponent(i)
    
    def addComponents(self,clist):
        self.clearComponents()
        for c in clist:
            self.addComponent(c)
    
    def addComponent(self,name,index=None):
        
        self.clearResult()
        self.deactivateResultControls()
        
        self.trace("adding component "+str(name)) 
        
        if index is None:
            index=len(self.component_table)
            
        self.component_table[index]=name
        
        if name in self.MWB_CORRECTION_FACTORS:
            return False
               
        self.MWB_CORRECTION_FACTORS[name]=[0,0.5,1]
    
    def removeComponent(self,index):
        self.clearResult()
        self.deactivateResultControls()
        name=self.component_table[index]
        self.component_table.pop(index)
        self.MWB_CORRECTION_FACTORS.pop(name)
    
    def signalMWBSlider(self, *arg, **args):
        if not self.__updating_mwb_ctrls:
            self.__updating_mwb_ctrls=True
            for name in self.component_ctrl_table:
                
                c_l_dsb=self.component_ctrl_table[name][1]
                c_l_sld=self.component_ctrl_table[name][0]
                c_m_dsb=self.component_ctrl_table[name][3]
                c_m_sld=self.component_ctrl_table[name][2]
                c_h_dsb=self.component_ctrl_table[name][5]
                c_h_sld=self.component_ctrl_table[name][4]
                
                new_l_val=c_l_sld.value()/10000.0
                new_m_val=c_m_sld.value()/10000.0
                new_h_val=c_h_sld.value()/10000.0
                
                c_l_dsb.setValue(new_l_val)
                c_m_dsb.setValue(new_m_val)
                c_h_dsb.setValue(new_h_val)
                
                self.MWB_CORRECTION_FACTORS[name]=[new_l_val,new_m_val,new_h_val]
            self.updateWBCorrectionFactors()
            self.updateHistograhm2()
            self.__updating_mwb_ctrls=False
            
    def signalMWBSpinBox(self, *arg, **args):
        if not self.__updating_mwb_ctrls:
            self.__updating_mwb_ctrls=True
            for name in self.component_ctrl_table:
                
                c_l_dsb=self.component_ctrl_table[name][1]
                c_l_sld=self.component_ctrl_table[name][0]
                c_m_dsb=self.component_ctrl_table[name][3]
                c_m_sld=self.component_ctrl_table[name][2]
                c_h_dsb=self.component_ctrl_table[name][5]
                c_h_sld=self.component_ctrl_table[name][4]
                
                new_l_val=c_l_dsb.value()
                new_m_val=c_m_dsb.value()
                new_h_val=c_h_dsb.value()
                
                c_l_sld.setValue(int(new_l_val*10000))
                c_m_sld.setValue(int(new_m_val*10000))
                c_h_sld.setValue(int(new_h_val*10000))
                
                self.MWB_CORRECTION_FACTORS[name]=[new_l_val,new_m_val,new_h_val]
            self.updateWBCorrectionFactors()
            self.updateHistograhm2()
            self.__updating_mwb_ctrls=False
    
    def updateWBCorrectionFactors(self):
        
        hmax=0
        lmin=1
        
        for name in self.MWB_CORRECTION_FACTORS:
            
            l,m,h=self.MWB_CORRECTION_FACTORS[name]
            
            hmax=max(hmax,h)
            lmin=min(lmin,l)
            
            min_step=self.component_ctrl_table[name][1].singleStep()
            
            if (h - l)<=min_step:
                self.MWB_CORRECTION_FACTORS[name][0]=h-min_step
                self.MWB_CORRECTION_FACTORS[name][2]=l+min_step
        
        for name in self.MWB_CORRECTION_FACTORS:
            self.MWB_CORRECTION_FACTORS[name][0]-=lmin
            self.MWB_CORRECTION_FACTORS[name][2]+=(1-hmax)
            
        self.updateMWBControls()
    
    def updateMWBControls(self):
        self.__updating_mwb_ctrls=True
        for name in self.MWB_CORRECTION_FACTORS:
            l,m,h=self.MWB_CORRECTION_FACTORS[name]
            
            c_l_dsb=self.component_ctrl_table[name][1]
            c_l_sld=self.component_ctrl_table[name][0]
            c_m_dsb=self.component_ctrl_table[name][3]
            c_m_sld=self.component_ctrl_table[name][2]
            c_h_dsb=self.component_ctrl_table[name][5]
            c_h_sld=self.component_ctrl_table[name][4]

            c_l_sld.setValue(int(l*10000))
            c_m_sld.setValue(int(m*10000))
            c_h_sld.setValue(int(h*10000))      
            c_l_dsb.setValue(l)
            c_m_dsb.setValue(m)
            c_h_dsb.setValue(h)

        self.__updating_mwb_ctrls=False
    
    def buildMWBControls(self):
        
        self.levels_dlg.MWBScrollArea.setLayout(QtGui.QGridLayout())
        
        idx = 0
        
        l_lbl=Qt.QLabel(tr("shadows"))
        m_lbl=Qt.QLabel(tr("middletones"))
        h_lbl=Qt.QLabel(tr("lights"))
        
        self.levels_dlg.MWBScrollArea.layout().addWidget(l_lbl,0,1,1,2)
        self.levels_dlg.MWBScrollArea.layout().addWidget(h_lbl,0,3,1,2)
        self.levels_dlg.MWBScrollArea.layout().addWidget(m_lbl,0,5,1,2)
        
        l_lbl.setSizePolicy(Qt.QSizePolicy.Expanding,Qt.QSizePolicy.Minimum)
        m_lbl.setSizePolicy(Qt.QSizePolicy.Expanding,Qt.QSizePolicy.Minimum)
        h_lbl.setSizePolicy(Qt.QSizePolicy.Expanding,Qt.QSizePolicy.Minimum)
        
        l_lbl.setAlignment(QtCore.Qt.AlignHCenter)
        m_lbl.setAlignment(QtCore.Qt.AlignHCenter)
        h_lbl.setAlignment(QtCore.Qt.AlignHCenter)
        
        for i in self.component_table:
            
            idx+=1    
            
            name = self.component_table[i]
            
            c_lbl=Qt.QLabel(str(name))
            
            c_l_sld=Qt.QDial()
            c_l_dsb=Qt.QDoubleSpinBox()
            c_m_sld=Qt.QDial()
            c_m_dsb=Qt.QDoubleSpinBox()
            c_h_sld=Qt.QDial()
            c_h_dsb=Qt.QDoubleSpinBox()
            
            c_l_dsb.setDecimals(4)
            c_m_dsb.setDecimals(4)
            c_h_dsb.setDecimals(4)
            
            c_l_sld.setSingleStep(1)
            c_l_dsb.setSingleStep(0.0001)
            c_m_sld.setSingleStep(1)
            c_m_dsb.setSingleStep(0.0001)
            c_h_sld.setSingleStep(1)
            c_h_dsb.setSingleStep(0.0001)
            
            c_l_sld.setMaximum(10000)
            c_l_dsb.setMaximum(1.0)
            c_m_sld.setMaximum(10000)
            c_m_dsb.setMaximum(1.0)
            c_h_sld.setMaximum(10000)
            c_h_dsb.setMaximum(1.0)
            
            c_l_sld.setMinimum(0)
            c_l_dsb.setMinimum(0)
            c_m_sld.setMinimum(0)
            c_m_dsb.setMinimum(0)
            c_h_sld.setMinimum(0)
            c_h_dsb.setMinimum(0)
            
            c_l_sld.setValue(int(self.MWB_CORRECTION_FACTORS[name][0]*10000))
            c_l_dsb.setValue(self.MWB_CORRECTION_FACTORS[name][0])
            c_m_sld.setValue(int(self.MWB_CORRECTION_FACTORS[name][1]*10000))
            c_m_dsb.setValue(self.MWB_CORRECTION_FACTORS[name][1])
            c_h_sld.setValue(int(self.MWB_CORRECTION_FACTORS[name][2]*10000))
            c_h_dsb.setValue(self.MWB_CORRECTION_FACTORS[name][2])
            
            c_l_sld.valueChanged.connect(self.signalMWBSlider)
            c_l_dsb.valueChanged.connect(self.signalMWBSpinBox)
            c_m_sld.valueChanged.connect(self.signalMWBSlider)
            c_m_dsb.valueChanged.connect(self.signalMWBSpinBox)
            c_h_sld.valueChanged.connect(self.signalMWBSlider)
            c_h_dsb.valueChanged.connect(self.signalMWBSpinBox)
            
            self.component_ctrl_table[name]=(c_l_sld,c_l_dsb,c_m_sld,c_m_dsb,c_h_sld,c_h_dsb)
            
            self.trace("building controls for component "+str(name)) 
            
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_lbl,idx,0)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_l_sld,idx,1)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_l_dsb,idx,2)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_h_sld,idx,3)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_h_dsb,idx,4)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_m_sld,idx,5)
            self.levels_dlg.MWBScrollArea.layout().addWidget(c_m_dsb,idx,6)
            
            c_lbl.show()
            c_l_sld.show()
            c_l_dsb.show()
            c_m_sld.show()
            c_m_dsb.show()
            c_h_sld.show()
            c_h_dsb.show()
                                    
        self.trace("DONE\n")
    
    def clearMWBControls(self):
        self.trace("\nclearing MWB controls...\n")
        try:
            del self.component_ctrl_table
        except:
            pass
        
        self.component_ctrl_table={}
        
        if not (self.levels_dlg.MWBScrollArea.layout() is None):
            Qt.QWidget().setLayout(self.levels_dlg.MWBScrollArea.layout())
    
    def rebuildMWBControls(self):
        self.clearMWBControls()
        self.buildMWBControls()
        
    def updateChartColors(self):
        self.wnd.colorADUComboBox.clear ()
        for i in range(len(self.colors)):
            self.wnd.colorADUComboBox.addItem(self.colors[i][1])
            self.wnd.colorMagComboBox.addItem(self.colors[i][1])
            
    
    def updateSaveOptions(self, *args):       
        
        if self.save_dlg.radioButtonJpeg.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(True)
            self.save_dlg.groupBoxImageCompression.setEnabled(False)
            self.save_dlg.radioButtonFloat.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setCheckState(2)
            self.save_dlg.radioButtonInt.setChecked(True)
            self.save_dlg.radioButton32.setEnabled(False)
            self.save_dlg.radioButton64.setEnabled(False)
            self.save_dlg.comprFitsCheckBox.setEnabled(False)
            self.save_dlg.rgbFitsCheckBox.setEnabled(False)
            
            if (self.save_dlg.radioButton32.isChecked() or
                self.save_dlg.radioButton64.isChecked()):
                self.save_dlg.radioButton8.setChecked(True)
            
        elif self.save_dlg.radioButtonPng.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(False)
            self.save_dlg.groupBoxImageCompression.setEnabled(True)
            self.save_dlg.radioButtonFloat.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setCheckState(2)
            self.save_dlg.radioButtonInt.setChecked(True)
            self.save_dlg.radioButton32.setEnabled(False)
            self.save_dlg.radioButton64.setEnabled(False)
            self.save_dlg.comprFitsCheckBox.setEnabled(False)
            self.save_dlg.rgbFitsCheckBox.setEnabled(False)
            
            if (self.save_dlg.radioButton32.isChecked() or
                self.save_dlg.radioButton64.isChecked()):
                self.save_dlg.radioButton8.setChecked(True)
            
        elif self.save_dlg.radioButtonTiff.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(False)
            self.save_dlg.groupBoxImageCompression.setEnabled(False)
            self.save_dlg.radioButtonFloat.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setCheckState(2)
            self.save_dlg.radioButtonInt.setChecked(True)
            self.save_dlg.radioButton8.setEnabled(True)
            self.save_dlg.radioButton16.setEnabled(True)
            self.save_dlg.radioButton32.setEnabled(False)
            self.save_dlg.radioButton64.setEnabled(False)
            self.save_dlg.comprFitsCheckBox.setEnabled(False)
            self.save_dlg.rgbFitsCheckBox.setEnabled(False)
            if (self.save_dlg.radioButton32.isChecked() or
                self.save_dlg.radioButton64.isChecked()):
                self.save_dlg.radioButton8.setChecked(True)
            
        elif self.save_dlg.radioButtonFits.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(False)
            self.save_dlg.groupBoxImageCompression.setEnabled(False)
            self.save_dlg.radioButtonFloat.setEnabled(False)
            self.save_dlg.radioButtonInt.setEnabled(False)
            self.save_dlg.checkBoxUnsigned.setEnabled(False)        
            self.save_dlg.radioButton8.setEnabled(True)
            self.save_dlg.radioButton16.setEnabled(True)
            self.save_dlg.radioButton32.setEnabled(True)
            self.save_dlg.radioButton64.setEnabled(True)
            self.save_dlg.comprFitsCheckBox.setEnabled(True)
            self.save_dlg.rgbFitsCheckBox.setEnabled(True)
            
            if self.save_dlg.radioButton8.isChecked():
                self.save_dlg.radioButtonInt.setChecked(True)
                self.save_dlg.checkBoxUnsigned.setCheckState(2)
            elif self.save_dlg.radioButton16.isChecked():
                self.save_dlg.radioButtonInt.setChecked(True)
                self.save_dlg.checkBoxUnsigned.setCheckState(0)
            elif self.save_dlg.radioButton32.isChecked():
                self.save_dlg.radioButtonFloat.setChecked(True)
                self.save_dlg.checkBoxUnsigned.setCheckState(0)
            elif self.save_dlg.radioButton64.isChecked():
                self.save_dlg.radioButtonFloat.setChecked(True)
                self.save_dlg.checkBoxUnsigned.setCheckState(0)
            else:
                pass #should never happen
            
        elif self.save_dlg.radioButtonNumpy.isChecked():
            self.save_dlg.groupBoxImageQuality.setEnabled(False)
            self.save_dlg.groupBoxImageCompression.setEnabled(False)
            self.save_dlg.radioButtonFloat.setEnabled(True)
            self.save_dlg.radioButtonInt.setEnabled(True)
            self.save_dlg.checkBoxUnsigned.setEnabled(True)
            self.save_dlg.radioButton32.setEnabled(True)
            self.save_dlg.radioButton64.setEnabled(True)
            self.save_dlg.comprFitsCheckBox.setEnabled(False)
            self.save_dlg.rgbFitsCheckBox.setEnabled(False)
            
            if self.save_dlg.radioButtonFloat.isChecked():
                self.save_dlg.checkBoxUnsigned.setCheckState(0)
                self.save_dlg.checkBoxUnsigned.setEnabled(False)
            else:
                self.save_dlg.checkBoxUnsigned.setEnabled(True)
            
        else:
            pass #should never happen
        
            
        self.save_dlg.radioButtonFloat.toggled.connect(self.updateSaveOptions)
    
    def _generateOpenStrings(self):
        self.supported_formats = utils.getSupportedFormats()
        # all supported formats
        self.images_extensions = ' ('
        for ext in self.supported_formats.keys():
            self.images_extensions+='*'+str(ext)+' '
        self.images_extensions += ');;'
        
        ImageTypes={}
        # each format
        for ext in self.supported_formats.keys():
            key=str(self.supported_formats[ext])
            
            if key in ImageTypes:
                ImageTypes[key]+=' *'+str(ext)
            else:
                ImageTypes[key]=' *'+str(ext)

        for ext in ImageTypes:
            self.images_extensions+=tr('Image')+' '+ext+' : '+ImageTypes[ext]
            self.images_extensions+='('+ImageTypes[ext]+');;'
        
    def setPhaseInterpolationOrder(self,val):
        self.phase_interpolation_order=val
        
    def setInterpolationOrder(self,val):
        self.interpolation_order=val
        
    def setShowPhaseIamge(self, val):
        self.checked_show_phase_img=val

    def setLevelsRange(self, lrange):
        self.wnd.minLevelDoubleSpinBox.setValue(np.min(lrange))
        self.wnd.maxLevelDoubleSpinBox.setValue(np.max(lrange))

    def setMinLevel(self, val):
        self.levels_range[0]=val
        if val <= self.levels_range[1]-1:
            self.setDisplayLevelsFitMode(self.fit_levels)
        else:
            self.wnd.maxLevelDoubleSpinBox.setValue(val+1)
        
    def setMaxLevel(self, val):
        self.levels_range[1]=val
        if val >= self.levels_range[0]+1:
            self.setDisplayLevelsFitMode(self.fit_levels)
        else:
            self.wnd.minLevelDoubleSpinBox.setValue(val-1)
            
    def setDisplayLevelsFitMode(self, state=2):
        
        if state==0:
            self.wnd.minLevelDoubleSpinBox.hide()
            self.wnd.maxLevelDoubleSpinBox.hide()
            self.wnd.fitMinMaxCheckBox.setText(tr('contrast')+': '+tr('none'))
        elif state==1:
            self.wnd.minLevelDoubleSpinBox.hide()
            self.wnd.maxLevelDoubleSpinBox.hide()
            self.wnd.fitMinMaxCheckBox.setText(tr('contrast')+': '+tr('full'))
        else:
            self.wnd.minLevelDoubleSpinBox.show()
            self.wnd.maxLevelDoubleSpinBox.show()
            self.wnd.fitMinMaxCheckBox.setText(tr('contrast')+': '+tr('yes'))
               
        self.fit_levels=state
        
        if not (self.current_image is None):
            self.showImage(utils.arrayToQImage(self.current_image._original_data,
                                            bw_jet=self.use_colormap_jet,
                                            fit_levels=self.fit_levels,
                                            levels_range=self.levels_range))        
            self.setLevelsRange(self.levels_range)
            
        if not (self.ref_image is None) and self.manual_align:
            self.ref_image = utils.arrayToQImage(self.ref_image._original_data,
                                                 bw_jet=self.use_colormap_jet,
                                                 fit_levels=self.fit_levels,
                                                 levels_range=self.levels_range)
        self.qapp.processEvents()
        self.generateScaleMaps()
        self.wnd.colorBar.repaint()
        
    #slots for menu actions

    @QtCore.pyqtSlot(bool)
    def doLoadFiles(self, is_checked):
        self.loadFiles()

    @QtCore.pyqtSlot(bool)
    def doNewProject(self, is_checked):
        self.newProject()

    @QtCore.pyqtSlot(bool)
    def doSaveProjectAs(self, is_checked):
        self.saveProjectAs()

    @QtCore.pyqtSlot(bool)
    def doSaveProject(self, is_checked):
        self.saveProject()

    @QtCore.pyqtSlot(bool)
    def doLoadProject(self, is_checked):
        self.loadProject()

    @QtCore.pyqtSlot(bool)
    def doSetPreferences(self, is_checked):
        self.setPreferences()

    @QtCore.pyqtSlot(bool)
    def doShowAbout(self, is_checked):
        self.about_dlg.exec_()

    @QtCore.pyqtSlot(bool)
    def doShowUserMan(self, is_checked):
        self.showUserMan()
        
    @QtCore.pyqtSlot(bool)    
    def doSaveVideo(self, is_checked):
        self.saveVideo()
    
    def changeAlignMethod(self, idx):
        self.current_align_method=idx
        self.imageLabel.repaint()
        if idx == 0:
            self.wnd.phaseGroupBox.show()
            self.wnd.alignGroupBox.hide()
        elif idx ==1:
            self.wnd.phaseGroupBox.hide()
            self.wnd.alignGroupBox.show()
        else:
            self.wnd.phaseGroupBox.hide()
            self.wnd.alignGroupBox.hide()
            #for other possible impementations
            pass
        
    def setFloatPrecision(self, idx):
        if idx==0:
            self.ftype=np.float32
        elif idx==1:
            self.ftype=np.float64
        
        self.trace("setting float precision to " + str(self.ftype))
        
    def setJetmapMode(self,val):
        if val==0:
            self.use_colormap_jet=False
        else:
            self.use_colormap_jet=True
        
        if not(self.current_image is None):
            self.current_image = utils.arrayToQImage(self.current_image._original_data,
                                                     bw_jet=self.use_colormap_jet,
                                                     fit_levels=self.fit_levels,
                                                     levels_range=self.levels_range)
            self.generateScaleMaps()
            self.updateImage()  

    def showUserMan(self):
        webbrowser.open(os.path.join(paths.DOCS_PATH,'usermanual.html'))

    def setBiasMul(self,val):
        self.master_bias_mul_factor=val

    def setDarkMul(self,val):
        self.master_dark_mul_factor=val
        
    def setFlatMul(self,val):
        self.master_flat_mul_factor=val

    def _resetPreferencesDlg(self):
        idx=self.dlg.langComboBox.findData(self.__current_lang)
        self.dlg.langComboBox.setCurrentIndex(idx)
        
        self.dlg.useCustomLangCheckBox.setCheckState(self.custom_chkstate)
        
        self.dlg.fTypeComboBox.setCurrentIndex(self.ftype_idx)
        
        self.dlg.jetCheckBox.setCheckState(self.checked_colormap_jet)
        self.dlg.rgbFitsCheckBox.setCheckState(int(self.frame_open_args['rgb_fits_mode'])*2)
        self.dlg.decodeCR2CheckBox.setCheckState(int(self.frame_open_args['convert_cr2'])*2)

        self.dlg.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        self.dlg.rWSpinBox.setValue(self.autoalign_rectangle[0])
        self.dlg.rHSpinBox.setValue(self.autoalign_rectangle[1])

        self.dlg.maxPointsSpinBox.setValue(self.max_points)
        self.dlg.minQualityDoubleSpinBox.setValue(self.min_quality)
        
        self.dlg.autoSizeCheckBox.setCheckState(self.checked_autodetect_rectangle_size)
        
        self.dlg.langFileLineEdit.setText(self.__current_lang)
        self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
        self.dlg.wholeImageCheckBox.setChecked(self.auto_align_use_whole_image)
        self.dlg.autoSizeCheckBox.setChecked(self.checked_autodetect_rectangle_size)
        self.dlg.minQualitycheckBox.setCheckState(self.checked_autodetect_min_quality)

        self.dlg.autoFolderscheckBox.setCheckState(self.checked_seach_dark_flat)
        
        self.dlg.tempPathCheckBox.setCheckState(self.checked_custom_temp_dir)
        self.dlg.tempPathLineEdit.setText(self.custom_temp_path)
        self.dlg.compressedTempCheckBox.setCheckState(self.checked_compressed_temp)
        
        self.dlg.showPhaseImgCheckBox.setCheckState(self.checked_show_phase_img)
        self.dlg.phaseIntOrderSlider.setValue(self.phase_interpolation_order)
        self.dlg.intOrderSlider.setValue(self.interpolation_order)
        
        if self.checked_custom_temp_dir==2:
            self.temp_path=os.path.expandvars(self.custom_temp_path)
        else:
            self.temp_path=paths.TEMP_PATH
            
        
    def _set_save_video_dir(self):
        self.save_image_dir = str(Qt.QFileDialog.getExistingDirectory(self.dlg,
                                                                      tr("Choose the detination folder"),
                                                                      self.save_image_dir,
                                                                      self._dialog_options))
        self.dlg.videoSaveLineEdit.setText(self.save_image_dir)
        
    def _set_temp_path(self):
        self.custom_temp_path = str(Qt.QFileDialog.getExistingDirectory(self.dlg,
                                                                        tr("Choose the temporary folder"),
                                                                        self.temp_path,
                                                                        self._dialog_options))
        self.dlg.tempPathLineEdit.setText(self.custom_temp_path)
        
    def setPreferences(self):

        qtr = Qt.QTranslator()
        self.dlg.langComboBox.clear()
        for qmf in os.listdir(paths.LANG_PATH):
            fl = os.path.join(paths.LANG_PATH,qmf)
            if qtr.load(fl):
                self.dlg.langComboBox.addItem(qmf,fl)
        self._resetPreferencesDlg()
        
        
        
        v4l2_ctl = subprocess.Popen(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE)
        v4l2_ctl.wait()
        data = v4l2_ctl.stdout.read().split('):\n')
        del v4l2_ctl

        #OpenCV cannot list devices yet!
        self.dlg.devComboBox.clear()
        self.devices=[]
                
        for dev_file in os.listdir("/dev"):
            if (len(dev_file)>5) and (dev_file[:5]=="video"):
                dev=os.path.join("/dev",dev_file)
                try:
                    idx = int(dev_file[5:])
                except:
                    continue
                
                v4l2_ctl = subprocess.Popen(['v4l2-ctl', '--device='+dev,'--info'], stdout=subprocess.PIPE)
                v4l2_ctl.wait()
                data = v4l2_ctl.stdout.read().replace('\t','').split('\n')
                
                dev_name = "Unknown"
                bus = "unknown"
                for prop in data:
                    lprop = prop.lower()
                    if 'card type' in lprop:
                        dev_name = prop[prop.find(':')+1:].strip()
                    elif 'bus info' in lprop:
                        dev_bus = prop[prop.find(':')+1:].strip()
                        
                self.trace("Find video device "+str(idx)+" --> " + dev_name + " at bus ["+dev_bus+"]")
                name = dev_name+" ("+dev_bus+")" 
        
                
                self.devices.append({'name':name,'dev':dev,'id':idx})
                self.dlg.devComboBox.addItem(name)

        if self.current_cap_combo_idx < 0:
            self.current_cap_combo_idx=0

        self.dlg.devComboBox.setCurrentIndex(self.current_cap_combo_idx)

        if self.isPreviewing:
            current_tab_idx=self.dlg.tabWidget.currentIndex()
            self.dlg.tabWidget.setCurrentIndex(2)
            self.dlg.show()
            return True
        else:
           pass
            
        if self.dlg.exec_() == 1:
            #update settings
            r_w=int(self.dlg.rWSpinBox.value())
            r_h=int(self.dlg.rHSpinBox.value())
            self.custom_chkstate=int(self.dlg.useCustomLangCheckBox.checkState())
            self.max_points=int(self.dlg.maxPointsSpinBox.value())
            self.min_quality=float(self.dlg.minQualityDoubleSpinBox.value())
            self.autoalign_rectangle=(r_w, r_h)
            self.save_image_dir = str(self.dlg.videoSaveLineEdit.text())
            self.current_cap_combo_idx=int(self.dlg.devComboBox.currentIndex())
            self.current_cap_device_idx=self.devices[self.current_cap_combo_idx]['id']
            self.auto_align_use_whole_image=int(self.dlg.wholeImageCheckBox.checkState())
            self.checked_autodetect_rectangle_size=int(self.dlg.autoSizeCheckBox.checkState())
            self.checked_colormap_jet=int(self.dlg.jetCheckBox.checkState())
            self.frame_open_args['rgb_fits_mode']=(int(self.dlg.rgbFitsCheckBox.checkState())==2)
            self.frame_open_args['convert_cr2']=(int(self.dlg.decodeCR2CheckBox.checkState())==2)
            self.checked_autodetect_min_quality=int(self.dlg.minQualitycheckBox.checkState())
            self.checked_seach_dark_flat=int(self.dlg.autoFolderscheckBox.checkState())
            self.ftype_idx=int(self.dlg.fTypeComboBox.currentIndex())
            self.checked_custom_temp_dir=int(self.dlg.tempPathCheckBox.checkState())
            self.checked_compressed_temp=int(self.dlg.compressedTempCheckBox.checkState())
            self.custom_temp_path=str(self.dlg.tempPathLineEdit.text())
            self.saveSettings()
            
            if self.checked_custom_temp_dir==2:
                self.temp_path=self.custom_temp_path
            else:
                self.temp_path=paths.TEMP_PATH
            
            return True
        else:
            #discard changes
            self._resetPreferencesDlg()
            return False
            
    def getDeviceInfo(self,idx):
        if idx >= 0:
            there_is_an_error=False
            if not self.isPreviewing:
                i=self.devices[self.current_cap_combo_idx]['id']
                self.current_cap_device.open(i)
                self.current_cap_device_idx=i
            
                       
            if self.current_cap_device.isOpened():
                try:
                    self.device_propetyes=utils.getV4LDeviceProperties(self.devices[idx]['dev'])
                except Exception as exc:
                    there_is_an_error=True
                    self.device_propetyes={}
                    
                
                w = int(self.current_cap_device.get(3))
                h = int(self.current_cap_device.get(4))
                self.resolution=str(w)+'x'+str(h)

                #setting up control interface
                try:
                    keys=self.device_propetyes['formats'].keys()
                    keys.sort()
                    self.format=self._setParamMenu(self.dlg.formatComboBox, keys, self.format)
                except Exception as exc:
                    pass
                
                try:
                    keys=self.device_propetyes['formats'][self.format].keys()
                    keys.sort()

                    self.resolution=self._setParamMenu(self.dlg.resolutionComboBox, keys, self.resolution)
                except Exception as exc:
                    there_is_an_error=True
                
                try:
                    keys=self.device_propetyes['formats'][self.format][self.resolution]['fps']
                    keys.sort()
                    keys.reverse()
                    
                    self.fps=self._setParamMenu(self.dlg.fpsComboBox, keys, self.fps)
                except Exception as exc:
                    pass
                
                try:
                    keys=self.device_propetyes['exposure_auto']['menu'].keys()
                    keys.sort()
                    self.exposure_type=self._setParamMenu(self.dlg.expTypeComboBox, keys, self.exposure_type)
                except Exception as exc:
                    pass
                
                if there_is_an_error:
                    utils.showWarningMsgBox(tr("The selected device seems to be broken\n and may not fully work!"))
                
                self._setParamLimits(self.dlg.expSlider,self.dlg.expSpinBox,'exposure_absolute')
                self._setParamLimits(self.dlg.gainSlider,self.dlg.gainSpinBox,'gain')
                self._setParamLimits(self.dlg.gammaSlider,self.dlg.gammaSpinBox,'gamma')
                self._setParamLimits(self.dlg.contrastSlider,self.dlg.contrastSpinBox,'contrast')
                self._setParamLimits(self.dlg.brightnessSlider,self.dlg.brightnessSpinBox,'brightness')
                self._setParamLimits(self.dlg.saturationSlider,self.dlg.saturationSpinBox,'saturation')
                self._setParamLimits(self.dlg.hueSlider,self.dlg.hueSpinBox,'hue')
                self._setParamLimits(self.dlg.sharpSlider,self.dlg.sharpSpinBox,'sharpness')
                        
            if not self.isPreviewing:
                self.current_cap_device.release()
    
    def _setParamMenu(self, combo, keys, def_val):
        combo.clear()
        
        for i in keys:
            combo.addItem(str(i))
        try:    
            if ((def_val not in keys) and 
                (combo.currentIndex()>=0) and
                (combo.currentIndex() < len(keys))):
                 def_val=keys[combo.currentIndex()]
            else:
                index=combo.findText(str(def_val))
                combo.setCurrentIndex(index)
            return def_val
        except Exception as exc:
            utils.showWarningMsgBox(tr("The selected device seems to be broken\n and may not fully work!"),parent=self.wnd)
            self.trace("The selected capture device seems to be broken and may not fully work!")
            self.trace(str(exc))

    def _setParamLimits(self, slider, spin, key):
        if key not in self.device_propetyes:
            slider.setEnabled(False)
            spin.setEnabled(False)
            return False
        else:
            slider.setEnabled(True)
            spin.setEnabled(True)
        keys=self.device_propetyes[key]
        if not(keys['min'] is None):
            slider.setMinimum(int(keys['min']))
            spin.setMinimum(int(keys['min']))
        if not(keys['max'] is None):
            slider.setMaximum(int(keys['max']))
            spin.setMaximum(int(keys['max']))
        if not(keys['value'] is None):
            slider.setValue(int(keys['value']))
            spin.setValue(int(keys['value']))
        elif not(keys['default'] is None):
            slider.setValue(int(keys['default']))
            spin.setValue(int(keys['default']))             

    def deviceFormatChanged(self,idx):
        if idx>0:
            self.old_format=self.format
            self.format=str(self.dlg.formatComboBox.itemText(idx))
            keys=self.device_propetyes['formats'][self.format].keys()
            keys.sort()
            self.resolution=self._setParamMenu(self.dlg.resolutionComboBox, keys, self.resolution)
            device=self.devices[self.current_cap_combo_idx]['dev']
            _4CC = cv2.cv.FOURCC(*list(self.format[0:4]))
            self.current_cap_device.set(cv2.cv.CV_CAP_PROP_FOURCC,_4CC)
            #utils.setV4LFormat(device,'pixelformat='+self.format)
                        
    def deviceResolutionChanged(self, idx):
        if idx>=0:
            self.resolution=str(self.dlg.resolutionComboBox.itemText(idx))
            keys=self.device_propetyes['formats'][self.format][self.resolution]['fps']
            keys.sort()
            keys.reverse()
            self.fps=self._setParamMenu(self.dlg.fpsComboBox, keys, self.fps)
            device=self.devices[self.current_cap_combo_idx]['dev']
            size=self.resolution.split('x')
            self.current_cap_device.set(3,int(size[0]))
            self.current_cap_device.set(4,int(size[1]))

    def deviceFpsChanged(self, idx):
        if idx>=0:
            self.fps=str(self.dlg.fpsComboBox.itemText(idx))
            device=self.devices[self.current_cap_combo_idx]['dev']
            fps = float(self.fps.split(' ')[0])
            self.current_cap_device.set(cv2.cv.CV_CAP_PROP_FPS,fps)
            
            actual_fps = utils.getV4LFps(device)

            if actual_fps != fps:
                #the fps is not set correclty
                self.statusBar.showMessage(tr("Sorry, but Fps cannot be changed on this device"))
                new_idx=self.dlg.fpsComboBox.findText(str(actual_fps)+" fps")
                self.dlg.fpsComboBox.setCurrentIndex(new_idx)
                
    def deviceExposureTypeChanged(self, idx):
        if idx>=0:
            self.exposure_type=str(self.dlg.expTypeComboBox.itemText(idx))
            device=self.devices[self.current_cap_combo_idx]['dev']
            value=self.device_propetyes['exposure_auto']['menu'][self.exposure_type]
            utils.setV4LCtrl(device,'exposure_auto',value)

    def deviceExposureChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'exposure_absolute',value)
        
    def deviceGainChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'gain',value)

    def deviceContrastChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'contrast',value)

    def deviceBrightnessChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'brightness',value)

    def deviceSaturationChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'saturation',value)
        
    def deviceHueChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'hue',value)
        
    def deviceSharpnessChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'sharpness',value)
        
    def deviceGammaChanged(self, value):
        device=self.devices[self.current_cap_combo_idx]['dev']
        utils.setV4LCtrl(device,'gamma',value)
        
    def capture(self, enabled=False, origin=None):
        
        if (not enabled) and self.current_cap_device.isOpened():
            self.wasCanceled=True
            return
        elif not enabled:
            self.wasCanceled=False
            return

        if origin is None:
            if ((self.current_cap_device_idx == -1) or
                (self.save_image_dir is None)):
                current_tab_idx=self.dlg.tabWidget.currentIndex()
                self.dlg.tabWidget.setCurrentIndex(2)
                if not self.setPreferences():
                    self.current_cap_device_idx = -1
                    self.wnd.captureGroupBox.setChecked(False)
                    utils.showErrorMsgBox(tr("No capture device selected"))
                    return False
                self.dlg.tabWidget.setCurrentIndex(current_tab_idx)
            self.current_cap_device.open(self.current_cap_device_idx)
        else:
            pass

        if self.current_cap_device.isOpened():           
            self.isPreviewing = True
            self.wnd.framesGroupBox.setEnabled(False)
            self._photo_time_clock=time.clock()
            while(not(self.wasCanceled)):
                self.qapp.processEvents()
                img = self.current_cap_device.read()
                if (img[0]==True):
                    self.__processCaptured(img[1])
                    if self.shooting:
                        self.shooting=False
                        if self._dismatchMsgBox(img[1]):
                            continue
                        ftime=time.strftime('%Y%m%d%H%M%S')
                        mstime='{0:05d}'.format(int((time.clock()-self._photo_time_clock)*100))
                        name=os.path.join(self.save_image_dir,ftime+mstime+'.tiff')
                        cv2.imwrite(name,img[1])
                        frm=utils.Frame(name, data=img[1])
                        
                        self.framelist.append(frm)
                        
                        q=Qt.QListWidgetItem(os.path.basename(name),self.wnd.listWidget)
                        q.setCheckState(2)
                        q.setToolTip(name)
                        frm.addProperty('listItem',q)
                        self.wnd.listWidget.setCurrentItem(q)
                        self._unlock_cap_ctrls()

                del img

            self.isPreviewing = False
            self.wasCanceled=False
            self.current_cap_device.release()
            self.wnd.framesGroupBox.setEnabled(True)
            self.clearImage()
            
            if len(self.framelist)>0:
                self.wnd.listWidget.setCurrentRow(0)
                self.listItemChanged(0)

        else:
            if origin is None:
                utils.showErrorMsgBox(tr("Cannot open current capture device!"))
            else:
                utils.showErrorMsgBox(tr("Cannot open this video file."))            
            return False
                    
    def _unlock_cap_ctrls(self):
        self.wnd.remPushButton.setEnabled(True)
        self.wnd.clrPushButton.setEnabled(True)
        self.wnd.listCheckAllBtn.setEnabled(True)
        self.wnd.listUncheckAllBtn.setEnabled(True)
        self.wnd.flatAddPushButton.setEnabled(True)
        self.wnd.darkAddPushButton.setEnabled(True)
        self.wnd.flatAddPushButton.setEnabled(True)
        self.wnd.masterBiasCheckBox.setEnabled(True)
        self.wnd.masterDarkCheckBox.setEnabled(True)
        self.wnd.masterFlatCheckBox.setEnabled(True)
        self.wnd.rawGroupBox.setChecked(False)
        
        if self.framelist[0].isRGB():
            self.wnd.rawGroupBox.setEnabled(False)
        else:
            self.wnd.rawGroupBox.setEnabled(True)
        
    def _dismatchMsgBox(self,img):
        imw = img.shape[1]
        imh = img.shape[0]

        if len(img.shape)==2:
            dep='L'
        elif (len(img.shape)==3) and img.shape[-1]==3:
            dep='RGB'
        else:
            dep='RGBA'
            
        if len(self.framelist)>0:
            if((imw != self.currentWidth) or
               (imh != self.currentHeight) or
               (dep != self.currentDepht[0:3])):
                utils.showErrorMsgBox(tr("Frame size or number of channels does not match.\n"),
                                      tr('current size=')+
                                      str(self.currentWidth)+'x'+str(self.currentHeight)+
                                      tr(' image size=')+
                                      str(imw)+'x'+str(imh)+'\n'+
                                      tr('current channels=')+str(self.currentDepht)+
                                      tr(' image channels=')+str(dep),
                                      parent=self.wnd)
                return True
            else:
                return False
        else:
            self.currentWidth=imw
            self.currentHeight=imh
            self.currentDepht=dep
            return False
            
    def oneShot(self):
        self.shooting=True
                        
    def __processCaptured(self, img):
        
        if len(img.shape)==3:
            self.wnd.colorBar._is_rgb=True
        else:
            self.wnd.colorBar._is_rgb=False
        
        self.showImage(utils.arrayToQImage(img,2,1,0, bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels,levels_range=self.levels_range))
        if self.wasStarted:
            self.wnd.stopCapturePushButton.show()
            self.wnd.capturePushButton.hide()
            if not self.wasStopped:
                if not self.writing:
                    self.video_url = os.path.join(self.save_image_dir,time.strftime('%Y-%m-%d@%H:%M:%S'))
                    self.wnd.singleShotPushButton.setEnabled(False)
                    self.captured_frames=0
                    self.writing=True
                    self.max_captured_frames=self.wnd.frameCountSpinBox.value()
                    
                    if self._dismatchMsgBox(img):
                        self.stopped()
                        return False

                    if not (os.path.isdir(self.video_url)):
                        os.makedirs(self.video_url)
                        
                    self.wnd.maxCapturedCheckBox.setEnabled(False)
                    self.wnd.singleShotPushButton.setEnabled(False)
                else:
                    self.captured_frames+=1
                    
                    name=os.path.join(self.video_url,'{0:05d}'.format(self.captured_frames)+'.tiff')
                    cv2.imwrite(name,img)
                    
                    frm = utils.Frame(name,0,skip_loading=True, **self.frame_open_args)
                    frm.addProperty('UTCEPOCH',utils.getCreationTime(name))
                    try:
                        frm.width=img.shape[1]
                        frm.height=img.shape[0]
                    except Exception:
                        self.trace( "Cannot retrieve image size!")
                        frm.width=0
                        frm.height=0
                        
                    if (len(img.shape)==3) and (img.shape[2]==3):
                        frm.mode='RGB'
                        frm.width=img.shape[1]
                        frm.height=img.shape[0]
                    elif (len(img.shape)==2):
                        frm.mode='L'
                    else:
                        frm.mode='???'
                        self.trace("Warning: unknown image format")
                        
                    self.framelist.append(frm)
                    
                    q=Qt.QListWidgetItem(os.path.basename(name),self.wnd.listWidget)
                    q.setCheckState(2)
                    q.setToolTip(name)
                    q.exif_properties=frm.properties
                    
                    self.wnd.listWidget.setCurrentItem(q)
                    
                    
                    if(self.wnd.maxCapturedCheckBox.checkState()==2):
                        self.max_captured_frames-=1
                        if self.max_captured_frames <= 0:
                            self.stopped()
                        elif self.captured_frames%5==0:
                            self.wnd.frameCountSpinBox.setValue(self.max_captured_frames)
                    elif self.captured_frames%5==0:
                        self.wnd.frameCountSpinBox.setValue(self.captured_frames)

            else:
                self.writing=False
                self.wnd.singleShotPushButton.setEnabled(True)
                self.wnd.maxCapturedCheckBox.setEnabled(True)
                self.wnd.singleShotPushButton.setEnabled(True)
                self.wnd.stopCapturePushButton.hide()
                self.wnd.capturePushButton.show()
                self.wasStarted=False
                if (len(self.framelist)>0):
                    self.wnd.frameCountSpinBox.setValue(self.captured_frames)
                    self.wnd.listWidget.setCurrentRow(0)
                    self._unlock_cap_ctrls()

    def useMasterBias(self,state):        
        if state == 2:
            self.wnd.masterBiasGroupBox.setEnabled(True)
            self.wnd.masterBiasGroupBox.show()
            self.wnd.biasFramesGroupBox.setEnabled(False)
            self.wnd.biasFramesGroupBox.hide()
        else:
            self.wnd.masterBiasGroupBox.setEnabled(False)
            self.wnd.masterBiasGroupBox.hide()
            self.wnd.biasFramesGroupBox.setEnabled(True)
            self.wnd.biasFramesGroupBox.show()

    def loadMasterBias(self):
        open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
        master_bias_file = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                              tr("Select master-dark file"),
                                                              self.current_dir,
                                                              open_str,
                                                              None,
                                                              self._dialog_options
                                                              )
                              )
        if os.path.isfile(master_bias_file):
           try:
               i = utils.Frame(master_bias_file, **self.frame_open_args)
               if not i.is_good:
                   utils.showErrorMsgBox(tr("Cannot open image")+" \""+str(i.url)+"\"",parent=self.wnd)
                   return False
               imw = i.width
               imh = i.height
               dep = i.mode
               if ((self.currentWidth == imw) and
                   (self.currentHeight == imh) and
                   (self.currentDepht == dep)):
                   self.master_bias_file=i.url
                   self.wnd.masterBiasLineEdit.setText(i.url)
               else:
                   utils.showErrorMsgBox(tr("Cannot use this file:")+tr(" size or number of channels does not match!"),
                                         tr('current size=')+
                                         str(self.currentWidth)+'x'+str(self.currentHeight)+'\n'+
                                         tr('image size=')+
                                         str(imw)+'x'+str(imh)+'\n'+
                                         tr('current channels=')+str(self.currentDepht)+'\n'+
                                         tr('image channels=')+str(dep),
                                         parent=self.wnd)
                                                     
               del i
           except Exception as exc:
               self.trace(str(exc))
               utils.showErrorMsgBox("",exc)

    def useMasterDark(self,state):        
        if state == 2:
            self.wnd.masterDarkGroupBox.setEnabled(True)
            self.wnd.masterDarkGroupBox.show()
            self.wnd.darkFramesGroupBox.setEnabled(False)
            self.wnd.darkFramesGroupBox.hide()
        else:
            self.wnd.masterDarkGroupBox.setEnabled(False)
            self.wnd.masterDarkGroupBox.hide()
            self.wnd.darkFramesGroupBox.setEnabled(True)
            self.wnd.darkFramesGroupBox.show()

    def loadMasterDark(self):
        open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
        master_dark_file = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                              tr("Select master-dark file"),
                                                              self.current_dir,
                                                              open_str,
                                                              None,
                                                              self._dialog_options
                                                              )
                              )
        if os.path.isfile(master_dark_file):
           try:
               i = utils.Frame(master_dark_file, **self.frame_open_args)
               if not i.is_good:
                   utils.showErrorMsgBox(tr("Cannot open image")+" \""+str(i.url)+"\"",parent=self.wnd)
                   return False
               imw = i.width
               imh = i.height
               dep = i.mode
               if ((self.currentWidth == imw) and
                   (self.currentHeight == imh) and
                   (self.currentDepht == dep)):
                   self.master_dark_file=i.url
                   self.wnd.masterDarkLineEdit.setText(i.url)
               else:
                   utils.showErrorMsgBox(tr("Cannot use this file:")+tr(" size or number of channels does not match!"),
                                         tr('current size=')+
                                         str(self.currentWidth)+'x'+str(self.currentHeight)+'\n'+
                                         tr('image size=')+
                                         str(imw)+'x'+str(imh)+'\n'+
                                         tr('current channels=')+str(self.currentDepht)+'\n'+
                                         tr('image channels=')+str(dep),
                                         parent=self.wnd)
               del i
           except Exception as exc:
               self.trace(str(exc))
               utils.showErrorMsgBox("",exc)
            
    def useMasterFlat(self,state):        
        if state == 2:
            self.wnd.masterFlatGroupBox.setEnabled(True)
            self.wnd.masterFlatGroupBox.show()
            self.wnd.flatFramesGroupBox.setEnabled(False)
            self.wnd.flatFramesGroupBox.hide()
        else:
            self.wnd.masterFlatGroupBox.setEnabled(False)
            self.wnd.masterFlatGroupBox.hide()
            self.wnd.flatFramesGroupBox.setEnabled(True)
            self.wnd.flatFramesGroupBox.show()
    
    def loadMasterFlat(self):
        open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
        master_flat_file = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                              tr("Select master-flatfield file"),
                                                              self.current_dir,
                                                              open_str,
                                                              None,
                                                              self._dialog_options
                                                              )
                              )
        if os.path.isfile(master_flat_file):
           try:
               i = utils.Frame(master_flat_file, **self.frame_open_args)
               if not i.is_good:
                   utils.showErrorMsgBox(tr("Cannot open image")+" \""+str(i.url)+"\"",parent=self.wnd)
                   return False
               imw = i.width
               imh = i.height
               dep = i.mode
               if ((self.currentWidth == imw) and
                   (self.currentHeight == imh) and
                   (self.currentDepht == dep)):
                   self.master_flat_file=i.url
                   self.wnd.masterFlatLineEdit.setText(i.url)
               else:
                   utils.showErrorMsgBox(tr("Cannot use this file:")+tr(" size or number of channels does not match!"),
                                         tr('current size=')+
                                         str(self.currentWidth)+'x'+str(self.currentHeight)+'\n'+
                                         tr('image size=')+
                                         str(imw)+'x'+str(imh)+'\n'+
                                         tr('current channels=')+str(self.currentDepht)+'\n'+
                                         tr('image channels=')+str(dep),
                                         parent=self.wnd)
               del i
           except Exception as exc:
               self.trace(str(exc))
               utils.showErrorMsgBox("",exc)
               
        
    #closeEvent callback
    def mainWindowCloseEvent(self, event):
        if self._fully_loaded:
            val = utils.showYesNoMsgBox(tr("Do you really want to quit?"),
                                        tr("All unsaved changes will be lost!"),
                                        parent=self.wnd)
            
            if val == Qt.QMessageBox.Yes:
                self.stopped()
                self.canceled()
                self.saveSettings()
                if os.path.exists(paths.TEMP_PATH):
                    shutil.rmtree(paths.TEMP_PATH)
                return self.wnd.__closeEvent__(event)
            elif val == Qt.QMessageBox.No:
                event.ignore()
            else:
                return self.wnd.__closeEvent__(event)
        else:
            event.ignore()
    
    def saveSettings(self):
        settings = Qt.QSettings()

        settings.beginGroup("mainwindow")
        settings.setValue("geometry", self.wnd.saveGeometry())
        settings.setValue("window_state", self.wnd.saveState())
        settings.endGroup()
        
        settings.beginGroup("options");
        qpoint=Qt.QPoint(self.autoalign_rectangle[0],self.autoalign_rectangle[1])
        settings.setValue("autoalign_rectangle", qpoint)
        settings.setValue("autodetect_rectangle", int(self.dlg.autoSizeCheckBox.checkState()))
        settings.setValue("autodetect_quality", int(self.dlg.minQualitycheckBox.checkState()))
        settings.setValue("max_align_points",int(self.max_points))
        settings.setValue("min_point_quality",float(self.min_quality))
        settings.setValue("use_whole_image", int(self.dlg.wholeImageCheckBox.checkState()))
        settings.setValue("use_colormap_jet", int(self.dlg.jetCheckBox.checkState()))
        settings.setValue("auto_rgb_fits", int(self.dlg.rgbFitsCheckBox.checkState()))
        settings.setValue("auto_convert_cr2", int(self.dlg.decodeCR2CheckBox.checkState()))
        settings.setValue("auto_search_dark_flat",int(self.dlg.autoFolderscheckBox.checkState()))
        settings.setValue("sharp1",float(self.wnd.sharp1DoubleSpinBox.value()))
        settings.setValue("sharp2",float(self.wnd.sharp2DoubleSpinBox.value()))
        settings.setValue("phase_image",int(self.dlg.showPhaseImgCheckBox.checkState()))
        settings.setValue("phase_order",int(self.dlg.phaseIntOrderSlider.value()))
        settings.setValue("interpolation_order",int(self.dlg.intOrderSlider.value()))
        settings.endGroup()
        
        settings.beginGroup("settings")
        if self.dlg.useCustomLangCheckBox.checkState()==2:
            self.__current_lang = str(self.dlg.langFileLineEdit.text())
            settings.setValue("custom_language",2)
        else:
            idx=self.dlg.langComboBox.currentIndex()
            settings.setValue("custom_language",0)
            if idx >= 0:
                lang=self.dlg.langComboBox.itemData(idx)
                if type(lang) == Qt.QVariant:
                    self.__current_lang = str(lang.toString())
                else:
                    self.__current_lang = str(lang)
        settings.setValue("language_file",self.__current_lang)
        settings.setValue("images_save_dir",self.save_image_dir)
        settings.setValue("current_align_method",int(self.current_align_method))
        settings.setValue("float_precision",int(self.ftype_idx))
        settings.setValue("use_custom_temp_path",int(self.checked_custom_temp_dir))
        settings.setValue("custom_temp_path",str(self.custom_temp_path))
        settings.setValue("use_zipped_tempfiles",int(self.checked_compressed_temp))
        settings.endGroup()
        

    def loadSettings(self):
        
        settings = Qt.QSettings()
        settings.beginGroup("mainwindow");
        val=settings.value("geometry",None,QtCore.QByteArray)
        self.wnd.restoreGeometry(val)
        self.wnd.restoreState(settings.value("window_state",None,QtCore.QByteArray))
        settings.endGroup()

        settings.beginGroup("options");
        point=settings.value("autoalign_rectangle",None,Qt.QPoint)
        self.autoalign_rectangle=(point.x(),point.y())
        self.checked_autodetect_rectangle_size=settings.value("autodetect_rectangle",None,int)
        self.checked_autodetect_min_quality=settings.value("autodetect_quality",None,int)
        self.dlg.minQualitycheckBox.setCheckState(self.checked_autodetect_min_quality)
        self.auto_align_use_whole_image=settings.value("use_whole_image",None,int)
        self.dlg.wholeImageCheckBox.setCheckState(self.auto_align_use_whole_image)
        self.checked_colormap_jet=settings.value("use_colormap_jet",None,int)
        self.dlg.jetCheckBox.setCheckState(self.checked_colormap_jet)
        self.dlg.decodeCR2CheckBox.setCheckState(settings.value("auto_convert_cr2",None,int))
        self.dlg.rgbFitsCheckBox.setCheckState(settings.value("auto_rgb_fits",None,int))
        self.checked_seach_dark_flat=settings.value("auto_search_dark_flat",None,int)
        self.dlg.autoFolderscheckBox.setCheckState(self.checked_seach_dark_flat)
        self.max_points=int(settings.value("max_align_points",None,int))
        self.min_quality=float(settings.value("min_point_quality",None,float))
        sharp1=float(settings.value("sharp1",None,float))
        self.wnd.sharp1DoubleSpinBox.setValue(sharp1)
        sharp2=float(settings.value("sharp1",None,float))
        self.wnd.sharp2DoubleSpinBox.setValue(sharp2)
        self.checked_show_phase_img=int(settings.value("phase_image",None,int))
        self.phase_interpolation_order=int(settings.value("phase_order",None,int))
        self.interpolation_order=int(settings.value("interpolation_order",None,int))
        settings.endGroup()

        settings.beginGroup("settings");
        self.__current_lang = str(settings.value("language_file",None,str))
        self.custom_chkstate=int(settings.value("custom_language",None,int))
        self.save_image_dir = str(settings.value("images_save_dir",None,str))
        self.current_align_method=int(settings.value("current_align_method",None,int))
        self.ftype_idx=int(settings.value("float_precision",None,int))
        self.checked_custom_temp_dir=int(settings.value("use_custom_temp_path",None,int))
        self.custom_temp_path=str(settings.value("custom_temp_path",None,str))
        self.checked_compressed_temp=int(settings.value("use_zipped_tempfiles",None,int))
        settings.endGroup()

        self.wnd.alignMethodComboBox.setCurrentIndex(self.current_align_method)
        self.changeAlignMethod(self.current_align_method)

    ##resizeEvent callback
    def mainWindowResizeEvent(self, event):
        val = self.wnd.__resizeEvent__(event)# old implementation
        if self.zoom_fit:
            self.updateImage()    
        self.generateScaleMaps()
        return val

    #mouseMoveEvent callback    
    def imageLabelMouseMoveEvent(self, event):
        val = self.imageLabel.__mouseMoveEvent__(event)
        mx=event.x()
        my=event.y()
        x=Int(mx/self.actual_zoom)
        y=Int(my/self.actual_zoom)

        if not (self.current_image is None) and (not self.manual_align):
            if not (self.current_image._original_data is None):
                imshape = self.current_image._original_data.shape
                if ((y>=0) and (y < imshape[0]) and
                    (x>=0) and (x < imshape[1])):
                        pix_val=self.current_image._original_data[y,x]
                        self.current_pixel=(x,y)
                        self.wnd.colorBar.current_val=pix_val
                        self.wnd.colorBar.repaint()
            else:
                pix_val=None
                
        if self.panning:            
            sx = mx-self.panning_startig[0]
            sy = my-self.panning_startig[1]           
            
            self.viewHScrollBar.setValue(self.viewHScrollBar.value()-sx)
            self.viewVScrollBar.setValue(self.viewVScrollBar.value()-sy)
            
        if (self.tracking_align_point and 
            (self.image_idx>=0) and 
            (self.point_idx>=0)
           ):
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt[0]=x
            pnt[1]=y
            self.wnd.spinBoxXAlign.setValue(x)
            self.wnd.spinBoxYAlign.setValue(y)
            self.imageLabel.repaint()
        elif (self.tracking_star_point and 
             (self.star_idx>=0)
           ):
            pnt = self.starslist[self.star_idx]
            pnt[0]=x
            pnt[1]=y
            self.wnd.spinBoxXStar.setValue(x)
            self.wnd.spinBoxYStar.setValue(y)
            self.imageLabel.repaint()
        return val
    
    
    def imageViewerWheelEvent(self, event):
        if self.zoom_enabled:
            delta = np.sign(event.delta())*math.log10(self.zoom+1)/2.5
            mx=event.x()
            my=event.y()
            cx = self.wnd.imageViewer.width()/2.0
            cy = self.wnd.imageViewer.height()/2.0
            sx=(cx - mx)/2
            sy=(cy - my)/2
            self.viewHScrollBar.setValue(self.viewHScrollBar.value()-sx)
            self.viewVScrollBar.setValue(self.viewVScrollBar.value()-sy)
                        
            self.setZoom(self.zoom+delta)

            
        return Qt.QWheelEvent.accept(event)
    
    def imageLabelMousePressEvent(self, event):
        val = self.imageLabel.__mousePressEvent__(event)
        btn=event.button()
        
        if btn==1:
            self.wnd.imageViewer.setCursor(QtCore.Qt.ClosedHandCursor)
            self.imageLabel.setCursor(QtCore.Qt.ClosedHandCursor)
            self.panning=True
            self.panning_startig=(event.x(),event.y())
        elif btn==2:
            if self.showAlignPoints:
                self.tracking_align_point=True
            elif self.showStarPoints:
                self.tracking_star_point=True
        return val
    
    def imageLabelMouseReleaseEvent(self, event):
        val = self.imageLabel.__mouseReleaseEvent__(event)
        btn=event.button()
        x=Int(event.x()/self.actual_zoom)
        y=Int(event.y()/self.actual_zoom)
        if btn==1:
            self.panning=False
            self.wnd.imageViewer.setCursor(self.use_cursor)
            self.imageLabel.setCursor(self.use_cursor)
        elif btn==2:
            if self.showAlignPoints and self.point_idx >= 0:
                self.tracking_align_point=False
                pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
                pnt[0]=x
                pnt[1]=y
                self.wnd.spinBoxXAlign.setValue(x)
                self.wnd.spinBoxYAlign.setValue(y)
                self.imageLabel.repaint()
            elif self.showStarPoints and self.star_idx >= 0:
                self.tracking_star_point=False
                pnt = self.starslist[self.star_idx]
                pnt[0]=x
                pnt[1]=y
                self.wnd.spinBoxXStar.setValue(x)
                self.wnd.spinBoxYStar.setValue(y)
                self.imageLabel.repaint()
        return val
    
    #paintEvent callback for colorBar
    def colorBarPaintEvent(self, obj):
        val=self.wnd.colorBar.__paintEvent__(obj)

        if self.current_image is None:
            self.wnd.colorBar.setPixmap(Qt.QPixmap())
            return val
        
        if not(self.wnd.colorBar.current_val is None):
            painter = Qt.QPainter(self.wnd.colorBar)
            cb = self.wnd.colorBar
            
            _gpo=2 #geometric corrections
            _gno=5 #geometric corrections
            
            fnt_size=10
            painter.setFont(Qt.QFont("Arial", fnt_size))
            y=(cb.height()+fnt_size/2)/2 + 2
            max_txt=str(cb.max_val)
            self.statusLabelMousePos.setText('position='+str(self.current_pixel)+' value='+str(cb.current_val))        
            if cb._is_rgb == True:
                cb.setPixmap(Qt.QPixmap.fromImage(self.rgb_colormap))
                
                try:
                    xr = int((float(cb.current_val[0]-cb.min_val)/float(cb.max_val-cb.min_val))*(cb.width()-_gno))+_gpo
                except Exception:
                    xr = -1
                    
                try:
                    xg = int((float(cb.current_val[1]-cb.min_val)/float(cb.max_val-cb.min_val))*(cb.width()-_gno))+_gpo
                except Exception:
                    xg = -1
                
                try:
                    xb = int((float(cb.current_val[2]-cb.min_val)/float(cb.max_val-cb.min_val))*(cb.width()-_gno))+_gpo
                except Exception:
                    xb = -1
                painter.setCompositionMode(22)
                
                painter.setPen(QtCore.Qt.red)
                painter.drawLine(xr,4,xr,self.wnd.colorBar.height()-4)
                
                painter.setPen(QtCore.Qt.green)
                painter.drawLine(xg,4,xg,self.wnd.colorBar.height()-4)
                
                painter.setPen(QtCore.Qt.blue)
                painter.drawLine(xb,4,xb,self.wnd.colorBar.height()-4)
                                
                painter.setCompositionMode(0)
                painter.setPen(QtCore.Qt.white)
                painter.drawText(fnt_size-4,y,str(cb.min_val))
                painter.setPen(QtCore.Qt.black)
                painter.drawText(cb.width()-(fnt_size-2)*len(max_txt),y,max_txt)
                
            else:
                painter.setPen(QtCore.Qt.white)

                painter.setCompositionMode(0)
                
                cb.setPixmap(Qt.QPixmap.fromImage(self.bw_colormap))
                
                try:
                    x = int((float(cb.current_val-cb.min_val)/float(cb.max_val-cb.min_val))*(cb.width()-_gno))+_gpo
                except Exception:
                    x = -1
                
                painter.setCompositionMode(22)
                
                painter.drawLine(x,4,x,self.wnd.colorBar.height()-4)

                painter.drawText(fnt_size-4,y,str(cb.min_val))
                painter.drawText(cb.width()-(fnt_size-2)*len(max_txt),y,max_txt)

                painter.setCompositionMode(0)

            del painter
            
        return val
    
    def histoViewPaintEvent(self, obj):
        
        bins=255
        
        painter = Qt.QPainter(self.levels_dlg.histoView)
        
        xmin,xmax = self.getLevelsClippingRange()
        
        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(painter.window())
        
        utils.drawHistograhm(painter, self._hst, xmin, xmax, logY=self.levels_dlg.histLogViewCheckBox.checkState())
    
    def saveADUChart(self,clicked):
        self.saveChart( self.wnd.aduListWidget, 'adu_chart',name='ADU', y_inverted=False)
        
    def saveMagChart(self,clicked):
        self.saveChart( self.wnd.magListWidget, 'mag_chart',name='Mag', y_inverted=True)
    
    def saveChart(self, widget, title, name, y_inverted=False):
        chart = Qt.QImage(1600,1200,Qt.QImage.Format_ARGB32)
        fname=str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the chart"),
                                         os.path.join(self.current_dir,title+'.jpg'),
                                         "JPEG (*.jpg *.jpeg);;PNG (*.png);;PPM (*.ppm);;TIFF (*.tiff *.tif);;All files (*.*)",None,
                                         self._dialog_options))
        self.simplifiedLightCurvePaintEvent( widget,chart, name, y_inverted)
        chart.save(fname,quality=100)
        
    def aduLabelPaintEvent(self, obj):
        return self.simplifiedLightCurvePaintEvent(self.wnd.aduListWidget,self.wnd.aduLabel,'ADU',False)
    
    def magLabelPaintEvent(self, obj):
        return self.simplifiedLightCurvePaintEvent(self.wnd.magListWidget,self.wnd.magLabel,'Mag',True)
    
    def simplifiedLightCurvePaintEvent(self, lwig, lbl, name, inv):
        if self.use_image_time:
            return self.lightCurvePaintEvent( lwig, lbl, ('time',name), utils.getTimeStr, inverted=inv)
        else:
            return self.lightCurvePaintEvent( lwig, lbl, ('index',name), str, inverted=inv)
            
    def lightCurvePaintEvent(self, listWidget, surface, aname, xStrFunc=str, yStrFunc=utils.getSciStr, inverted=False):

        painter = Qt.QPainter(surface)
        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(painter.window())
        painter.setBrush(QtCore.Qt.NoBrush)
        
        x_off=60
        y_off=50
        
        if ('time' in self.lightcurve) and (False in self.lightcurve):
             
            data_x=np.array(self.lightcurve['time'],dtype=np.float64)

            if len(data_x)<2:
                return

            ymin=None
            ymax=None
            
            there_is_at_least_one_chart=False
            for i in range(listWidget.count()):
                q = listWidget.item(i)
                if q is None:
                    continue
                if q.checkState()==2:
                    there_is_at_least_one_chart=True
                    data_y=np.array(self.lightcurve[q.listindex[0]][q.listindex[1]]['data'])
                    errors_y=np.array(self.lightcurve[q.listindex[0]][q.listindex[1]]['error'])
                    
                    emax=2.0*errors_y.max()
                    
                    if data_y.shape[0]==0:
                        continue
                    
                    if len(data_y.shape)>1:
                        data_y=data_y[:,q.listindex[2]]
                
                    if ymin is None:
                        ymin=data_y.min()-emax
                    else:
                        ymin=min(ymin,data_y.min()-emax)
                
                    if ymax is None:
                        ymax=data_y.max()+emax
                    else:
                        ymax=max(ymax,data_y.max()+emax)
            
            
            if there_is_at_least_one_chart:
                utils.drawAxis(painter, (data_x.min(),data_x.max()), (ymin,ymax), x_offset=x_off, y_offset=y_off, axis_name=aname,
                               x_str_func=xStrFunc, y_str_func=yStrFunc, inverted_y=inverted)
            else:
                utils.drawAxis(painter, (0,1), (0,1), x_offset=x_off, y_offset=y_off, axis_name=aname,
                               x_str_func=xStrFunc, y_str_func=yStrFunc, inverted_y=inverted)
            
            count = 0;
            
            for i in range(listWidget.count()):
                q = listWidget.item(i)
                if q is None:
                    continue
                if q.checkState()==2:
                    data_y=np.array(self.lightcurve[q.listindex[0]][q.listindex[1]]['data'])
                    errors_y=np.array(self.lightcurve[q.listindex[0]][q.listindex[1]]['error'])
                    
                    if data_y.shape[0]==0:
                        continue
                    
                    if len(data_y.shape)>1:
                        data_y=data_y[:,q.listindex[2]]
                        errors_y=errors_y[:,q.listindex[2]]
                    utils.drawCurves(painter, data_x, data_y, (ymin,ymax), inverted_y=inverted,
                                     x_offset=x_off, y_offset=y_off,
                                     errors=errors_y,
                                     bar_type=q.chart_properties['bars'],
                                     line_type=q.chart_properties['line'],
                                     point_type=q.chart_properties['points'],
                                     color=q.chart_properties['color'],
                                     int_param=q.chart_properties['smoothing'],
                                     point_size=q.chart_properties['point_size'],
                                     line_width=q.chart_properties['line_width'])
    
    
        else:
            utils.drawAxis(painter, (0,1), (0,1),  x_offset=x_off, y_offset=y_off, axis_name=aname,
                               x_str_func=xStrFunc, y_str_func=yStrFunc, inverted_y=inverted)
            
    def getChartPoint(self,index):
        return utils.POINTS_TYPE[1+index%(len(utils.POINTS_TYPE)-1)]
            
    def getChartColor(self,index):
        try:
            return self.colors[index%len(self.colors)][0]
        except Exception:
            for i in self.colors:
                if i[1]==str(index):
                    return i[0]
                else:
                    raise ValueError('cannot find chart color '+str(index))
        
    def getChartColorIndex(self, color):
        for i in self.colors:
            if i[0]==color:
                return self.colors.index(i)
        raise ValueError('cannot find chart color '+str(color))


    def setCurrentADUCurveColor(self, idx):
        return self.setCurrentCurveColor(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurveColor(self, idx):
        return self.setCurrentCurveColor(idx, self.wnd.magListWidget, self.wnd.magLabel) 
        
    def setCurrentCurveColor(self, idx, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        q.chart_properties['color']=self.getChartColor(idx)
        surface.repaint()

    def setCurrentADUCurveLineType(self, idx):
        return self.setCurrentCurveLineType(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurveLineType(self, idx):
        return self.setCurrentCurveLineType(idx, self.wnd.magListWidget, self.wnd.magLabel) 
        
        
    def setCurrentCurveLineType(self, idx, listWidget, surface):
        q = listWidget.currentItem()

        if q is None:
            return
        
        try:
            linetype=utils.LINES_TYPE[idx]
        except:
            linetype=utils.LINES_TYPE[0]
            
        q.chart_properties['line']=linetype
        surface.repaint()

    def setCurrentADUCurvePointsType(self, idx):
        return self.setCurrentCurvePointsType(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurvePointsType(self, idx):
        return self.setCurrentCurvePointsType(idx, self.wnd.magListWidget, self.wnd.magLabel) 
        
    
    def setCurrentCurvePointsType(self, idx, listWidget, surface):
        q = listWidget.currentItem()

        if q is None:
            return
        try:
            pointstype=utils.POINTS_TYPE[idx]
        except:
            pointstype=utils.POINTS_TYPE[0]
            
        q.chart_properties['points']=pointstype
        surface.repaint()

    def setCurrentADUCurveBarsType(self, idx):
        return self.setCurrentCurveBarsType(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurveBarsType(self, idx):
        return self.setCurrentCurveBarsType(idx, self.wnd.magListWidget, self.wnd.magLabel) 
    
    def setCurrentCurveBarsType(self, idx, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        try:
            barstype=utils.BARS_TYPE[idx]
        except:
            barstype=utils.BARS_TYPE[0]          
            
        q.chart_properties['bars']=barstype
        surface.repaint()
        

    def setCurrentADUCurveSmooting(self, idx):
        return self.setCurrentCurveSmooting(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagCurveSmooting(self, idx):
        return self.setCurrentCurveSmooting(idx, self.wnd.magListWidget, self.wnd.magLabel) 
    
    def setCurrentCurveSmooting(self, val, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        q.chart_properties['smoothing']=val
        surface.repaint()
        
    def setCurrentADUPointSize(self, idx):
        return self.setCurrentPointSize(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagPointSize(self, idx):
        return self.setCurrentPointSize(idx, self.wnd.magListWidget, self.wnd.magLabel) 
    
    def setCurrentPointSize(self, val, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        q.chart_properties['point_size']=val
        surface.repaint()
        
    def setCurrentADULineWidth(self, idx):
        return self.setCurrentLineWidth(idx, self.wnd.aduListWidget, self.wnd.aduLabel) 
    
    def setCurrentMagLineWidth(self, idx):
        return self.setCurrentLineWidth(idx, self.wnd.magListWidget, self.wnd.magLabel) 
    
    def setCurrentLineWidth(self, val, listWidget, surface):
        q = listWidget.currentItem()
        
        if q is None:
            return
        
        q.chart_properties['line_width']=val
        surface.repaint()
        
    #mouseMoveEvent callback    
    def imageLabelMouseMoveEvent(self, event):
        val = self.imageLabel.__mouseMoveEvent__(event)
        mx=event.x()
        my=event.y()
        x=Int(mx/self.actual_zoom)
        y=Int(my/self.actual_zoom)

        if not (self.current_image is None) and (not self.manual_align):
            if not (self.current_image._original_data is None):
                imshape = self.current_image._original_data.shape
                if ((y>=0) and (y < imshape[0]) and
                    (x>=0) and (x < imshape[1])):
                        pix_val=self.current_image._original_data[y,x]
                        self.current_pixel=(x,y)
                        self.wnd.colorBar.current_val=pix_val
                        self.wnd.colorBar.repaint()
            else:
                pix_val=None
                
        if self.panning:            
            sx = mx-self.panning_startig[0]
            sy = my-self.panning_startig[1]           
            
            self.viewHScrollBar.setValue(self.viewHScrollBar.value()-sx)
            self.viewVScrollBar.setValue(self.viewVScrollBar.value()-sy)
            
        if (self.tracking_align_point and 
            (self.image_idx>=0) and 
            (self.point_idx>=0)
           ):
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt[0]=x
            pnt[1]=y
            self.wnd.spinBoxXAlign.setValue(x)
            self.wnd.spinBoxYAlign.setValue(y)
            self.imageLabel.repaint()
        elif (self.tracking_star_point and 
             (self.star_idx>=0)
           ):
            pnt = self.starslist[self.star_idx]
            pnt[0]=x
            pnt[1]=y
            self.wnd.spinBoxXStar.setValue(x)
            self.wnd.spinBoxYStar.setValue(y)
            self.imageLabel.repaint()
        return val
    
    def previewLabelPaintEvent(self, obj):
        val=self.levels_dlg.previewLabel.__paintEvent__(obj)
        
        if not (self._preview_data is None):
            w=float(self.levels_dlg.previewLabel.width())
            h=float(self.levels_dlg.previewLabel.height())
            ww=float(self._preview_image.width())
            hh=float(self._preview_image.height())
            
            target_rect=Qt.QRectF(0,0,w,h)
            
            if (w/h) <= (ww/hh):
                neww=hh*w/h
                newh=hh
            else:
                newh=ww*h/w
                neww=ww
                
            source_rect=Qt.QRectF((ww-neww)/2,(hh-newh)/2,neww,newh)
            
            painter = Qt.QPainter(self.levels_dlg.previewLabel)
            painter.drawImage(target_rect,self._preview_image,source_rect)
            
            #painter.drawImage(0,0,self._preview_image,(ww-neww)/2,(hh-newh)/2,neww,newh)
        return val
    
    #paintEvent callback
    def imageLabelPaintEvent(self, obj):
        val=self.imageLabel.__paintEvent__(obj)
        
        painter = Qt.QPainter(self.imageLabel)
        
        if not (self.current_image is None):
            painter.scale(self.actual_zoom,self.actual_zoom)
            painter.drawImage(0,0,self.current_image)
        
        if self.image_idx >=0:
            #draw the stars selected for light curves generation        
            self._drawStarPoints(painter)
                
        if (not self.manual_align):
            if (self.current_align_method==0) and (self.is_aligning):
                self._drawPhaseAlign(painter)
            elif (self.current_align_method==1) and (self.image_idx>=0):
                self._drawAlignPoints(painter)
                            
        else:
            self._drawDifference(painter)
        del painter
        return val

    def _drawStarPoints(self, painter):
        if(not self.showStarPoints):
            return False
        painter.setFont(Qt.QFont("Arial", 8))  
        
        
        cx = self.currentWidth/2.0
        cy = self.currentHeight/2.0

        img = self.framelist[self.image_idx]
        an2=img.angle*math.pi/180.0
            
        for i in self.starslist:           
                        
            di = dist(cx,cy,i[0],i[1])
            an = math.atan2((cy-i[1]),(cx-i[0]))
                        
            x = cx - di*math.cos(an+an2) + img.offset[0] + 0.5
            y = cy - di*math.sin(an+an2) + img.offset[1] + 0.5
            
            r1=i[3]
            r2=i[4]
            r3=i[5]
            
            if i[6]==True:
                painter.setCompositionMode(0)
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.setPen(QtCore.Qt.green)
            else:
                painter.setCompositionMode(28)
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.setPen(QtCore.Qt.white)
                
            painter.drawEllipse(Qt.QPointF(x,y),r1,r1)
            painter.drawEllipse(Qt.QPointF(x,y),r2,r2)
            painter.drawEllipse(Qt.QPointF(x,y),r3,r3)
            
            painter.setCompositionMode(0)
            rect=Qt.QRectF(x+r3-2,y+r3-2,60,15)
            painter.setBrush(QtCore.Qt.blue)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(rect)
            
            if i[6]==True:
                painter.setPen(QtCore.Qt.green)
            else:
                painter.setPen(QtCore.Qt.yellow)
                
            painter.drawText(rect,QtCore.Qt.AlignCenter,i[2])

    def _drawPhaseAlign(self, painter):
                
        painter.setCompositionMode(0)
        painter.setPen(QtCore.Qt.white)


        if not (self._phase_align_data is None):
            
            cx = self._phase_align_data[2][1]/2.0
            cy = self._phase_align_data[2][0]/2.0
               
            utils.drawMarker(painter, cx, cy,
                             7.0/self.actual_zoom,2.0/self.actual_zoom, False)
        
            px = cx - self._phase_align_data[0][0]
            py = cy - self._phase_align_data[0][1]
        
            painter.setPen(QtCore.Qt.red)
            utils.drawMarker(painter, px, py,
                             7.0/self.actual_zoom,2.0/self.actual_zoom, False)
        
        
    def _drawAlignPoints(self, painter):
        if(len(self.framelist) == 0) or (not self.showAlignPoints):
            return False
        painter.setFont(Qt.QFont("Arial", 8))  
        for i in self.framelist[self.image_idx].alignpoints:
                      
            x=i[0]+0.5
            y=i[1]+0.5
            
            painter.setCompositionMode(28)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtCore.Qt.white)
            utils.drawMarker(painter,x,y)
            painter.setCompositionMode(0)
            rect=Qt.QRectF(x+8,y+10,45,15)
            painter.setBrush(QtCore.Qt.blue)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(rect)
            painter.setPen(QtCore.Qt.yellow)
            painter.drawText(rect,QtCore.Qt.AlignCenter,i[2])
            rect=Qt.QRectF(x-self.autoalign_rectangle[0]/2,
                           y-self.autoalign_rectangle[1]/2,
                           self.autoalign_rectangle[0],
                           self.autoalign_rectangle[1])
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(rect)
            
    def _drawDifference(self,painter):
        if not (self.ref_image is None) and not (self.current_image is None):
            
            ref = self.framelist[self.ref_image_idx]
            img = self.framelist[self.dif_image_idx] 
            
            rot_center=(img.width/2.0,img.height/2.0)
           
            painter.drawImage(0,0,self.ref_image)
            painter.setCompositionMode(22)
                        
            x = (img.offset[0]-ref.offset[0])
            y = (img.offset[1]-ref.offset[1])
            
            #this is needed because the automatic aignment takes the first image available as
            #reference to calculate derotation
            alpha = self.framelist[self.wnd.listWidgetManualAlign.item(0).original_id].angle            
            
            cosa = math.cos(np.deg2rad(-alpha))
            sina = math.sin(np.deg2rad(-alpha))
            
            xi = x*cosa + y*sina
            yi = y*cosa - x*sina
                        
            painter.translate(rot_center[0]-xi,rot_center[1]-yi)
            
            painter.rotate(-img.angle+ref.angle)

            painter.drawImage(-int(rot_center[0]),-int(rot_center[1]),self.current_image)
            painter.setCompositionMode(0)
    
    def setZoomMode(self, val, check=False):
        
        if check:
            self.wnd.zoomCheckBox.setCheckState(val)
        
        if val is 0:
            self.wnd.zoomCheckBox.setText(tr('zoom: none'))
            self.wnd.zoomSlider.setEnabled(False)
            self.wnd.zoomDoubleSpinBox.setEnabled(False)
            self.zoom_enabled=False
            self.zoom_fit=False
        elif val is 1:
            self.wnd.zoomCheckBox.setText(tr('zoom: fit'))
            self.zoom_enabled=False
            self.zoom_fit=True
        else:
            self.wnd.zoomCheckBox.setText(tr('zoom: full'))
            self.wnd.zoomSlider.setEnabled(True)
            self.wnd.zoomDoubleSpinBox.setEnabled(True)
            self.zoom_enabled=True
            self.zoom_fit=False
        self.updateImage()
    
    def setZoom(self,zoom):
        
        if zoom <= self.wnd.zoomDoubleSpinBox.maximum():
            self.zoom=zoom
        else:
            self.zoom=self.wnd.zoomDoubleSpinBox.maximum()
            
        self.wnd.zoomDoubleSpinBox.setValue(self.zoom)
        self.wnd.zoomSlider.setValue(Int(self.zoom*100))
        
    def signalSliderZoom(self, value, update=False):
        self.zoom=(value/100.0)
        vp = self.getViewport()
        self.wnd.zoomDoubleSpinBox.setValue(self.zoom)
        if update:
            self.updateImage()

        self.setViewport(vp)
        
    def signalSpinZoom(self, value, update=True):
        self.zoom=value
        vp = self.getViewport()
        self.wnd.zoomSlider.setValue(Int(self.zoom*100))
        if update:
            self.updateImage()
        self.setViewport(vp)
        
    def getViewport(self):
        try:
            x = float(self.viewHScrollBar.value())/float(self.viewHScrollBar.maximum())
        except ZeroDivisionError:
            x = 0.5
        try:
            y = float(self.viewVScrollBar.value())/float(self.viewVScrollBar.maximum())
        except ZeroDivisionError:
            y = 0.5
            
        return (x,y)
    
    def setViewport(self,viewPoint):
        self.viewHScrollBar.setValue(viewPoint[0]*self.viewHScrollBar.maximum())
        self.viewVScrollBar.setValue(viewPoint[1]*self.viewVScrollBar.maximum())
        
    def updateResultImage(self):
        if not (self._stk is None):
            img = utils.arrayToQImage(self._stk,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels,levels_range=self.levels_range)
            self.showImage(img)
        else:
            self.clearImage()
        
    def showImage(self, image):
        del self.current_image
        self.current_image = image
        self.updateImage()
            
    def clearImage(self):
        del self.current_image
        self.current_image=None
        self.imageLabel.setPixmap(Qt.QPixmap())
        
    def generateScaleMaps(self):
        # bw or jet colormap
        data1 = np.arange(0,self.wnd.colorBar.width())*255.0/self.wnd.colorBar.width()
        data2 = np.array([data1]*(self.wnd.colorBar.height()-8))
        qimg = utils.arrayToQImage(data2,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels,levels_range=self.levels_range)
        self.bw_colormap = qimg

        #rgb colormap
        data1 = np.arange(0,self.wnd.colorBar.width())*255.0/self.wnd.colorBar.width()
        data2 = np.array([data1]*int((self.wnd.colorBar.height()-8)/3.0))
        hh=len(data2)
        data3 = np.zeros((3*hh,len(data1),3))
       
        data3[0:hh,0:,0]=data2
        data3[hh:2*hh,0:,1]=data2
        data3[2*hh:3*hh,0:,2]=data2
        
        qimg = utils.arrayToQImage(data3,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels,levels_range=self.levels_range)
        self.rgb_colormap = qimg

    def updateImage(self, paint=True, overrided_image=None):
        
        if not (overrided_image is None):
            current_image=overrided_image
        elif not(self.current_image is None):
            current_image=self.current_image
        else:
            return False
        
        imh = current_image.height()
        imw = current_image.width()

        try:
            self.wnd.colorBar.current_val=current_image._original_data[self.current_pixel[1],self.current_pixel[0]]
            self.wnd.colorBar.repaint()
        except Exception as exc:
            self.current_pixel=(0,0)

        if self.zoom_enabled:
            self.actual_zoom=self.zoom
        elif self.zoom_fit:
                        
            self.actual_zoom=min(float(self.wnd.imageViewer.width()-10)/imw,
                                 float(self.wnd.imageViewer.height()-10)/imh
                                )
                                
            self.wnd.zoomDoubleSpinBox.setValue(self.zoom)
        else:
            self.actual_zoom=1
            
        if paint:
            imh+=1
            imw+=1
            self.imageLabel.setMaximumSize(imw*self.actual_zoom,imh*self.actual_zoom)
            self.imageLabel.setMinimumSize(imw*self.actual_zoom,imh*self.actual_zoom)
            self.imageLabel.resize(imw*self.actual_zoom,imh*self.actual_zoom)
            self.imageLabel.update()
            if not(current_image._original_data is None):
                self.wnd.colorBar.max_val=current_image._original_data.max()
                self.wnd.colorBar.min_val=current_image._original_data.min()

                if (self.wnd.colorBar.max_val <=1) or self.fit_levels:
                    pass
                elif self.wnd.colorBar.max_val <= 255:
                    self.wnd.colorBar.max_val*=255.0/self.wnd.colorBar.max_val
                elif self.wnd.colorBar.max_val <= 65536:
                    self.wnd.colorBar.max_val*=65536.0/self.wnd.colorBar.max_val
                    
                if self.fit_levels:
                    pass
                elif self.wnd.colorBar.min_val > 0:
                    self.wnd.colorBar.min_val*=0
                
                if not self.wnd.colorBar.isVisible():
                    self.wnd.colorBar.show()
            else:
                self.wnd.colorBar.max_val=1
                self.wnd.colorBar.max_val=0
                if self.wnd.colorBar.isVisible():
                    self.wnd.colorBar.hide()
                
            #this shuold avoid division by zero
            if  self.wnd.colorBar.max_val ==  self.wnd.colorBar.min_val:
                self.wnd.colorBar.max_val=self.wnd.colorBar.max_val+1
                self.wnd.colorBar.min_val=self.wnd.colorBar.min_val-1
                
            #self.generateScaleMaps()
        #else:
            #return pix
    
    def setUpStatusBar(self):      
        self.progress = Qt.QProgressBar()
        self.progress.setRange(0,100)
        self.progress.setMaximumSize(400,25)
        self.cancelProgress=Qt.QPushButton(tr('cancel'))
        self.cancelProgress.clicked.connect(self.canceled)
        self.statusBar.addPermanentWidget(self.statusLabelMousePos)
        self.statusBar.addPermanentWidget(self.cancelProgress)
        self.statusBar.addPermanentWidget(self.progress)
        self.progress.hide()
        self.cancelProgress.hide()
        self.statusBar.showMessage(tr('Welcome!'))

    def lock(self, show_cancel = True):
        self.qapp.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.statusLabelMousePos.setText('')
        self.progress.show()
        
        if show_cancel:
            self.cancelProgress.show()
        else:
            self.cancelProgress.hide()
            
        self.wnd.toolBox.setEnabled(False)
        self.wnd.MainFrame.setEnabled(False)
        self.wnd.menubar.setEnabled(False)
        
    def unlock(self):
        self.statusBar.clearMessage()
        self.progress.hide()
        self.cancelProgress.hide()
        self.progress.reset()
        self.wnd.toolBox.setEnabled(True)
        self.wnd.MainFrame.setEnabled(True)
        self.wnd.menubar.setEnabled(True)
        self.qapp.restoreOverrideCursor()

    def canceled(self):
        self.wasCanceled=True

    def stopped(self):
        self.wasStopped=True

    def started(self):
        self.wasStarted=True
        self.wasStopped=False
    
    def loadFiles(self, newlist=None):

        oldlist=self.framelist[:]

        if newlist is None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            newlist=list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str,
                                                         None,
                                                         self._dialog_options)
                        )

        self.statusBar.showMessage(tr('Loading files, please wait...'))
        
        if len(newlist) == 0:
            return
        
        if len(self.framelist) > 0:
            imw = self.currentWidth
            imh = self.currentHeight
            dep = self.currentDepht[0:3]
        else:
            ref = utils.Frame(str(newlist[0]), **self.frame_open_args)
            if not ref.is_good:
                msgBox = Qt.QMessageBox(self.wnd)
                msgBox.setText(tr("Cannot open image")+" \""+str(ref.url)+"\"")
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
            imw = ref.width
            imh = ref.height
            dep = ref.mode
            
            del ref     
            
            self.currentWidth=imw
            self.currentHeight=imh
            self.currentDepht=dep
            
            self.updateBayerComponents()

            if self.dlg.autoSizeCheckBox.checkState()==2:
                r_w=int(self.currentWidth/10)
                r_h=int(self.currentHeight/10)
                r_l=max(r_w,r_h)
                self.autoalign_rectangle=(r_l,r_h)
                self.dlg.rWSpinBox.setValue(r_l)
                self.dlg.rHSpinBox.setValue(r_l)
            
            if 'RGB' in dep:
                self.wnd.colorBar._is_rgb=True
                self.wnd.colorBar.current_val=(0.0,0.0,0.0)
            else:
                self.wnd.colorBar._is_rgb=False
                self.wnd.colorBar.current_val=0.0
                
            self.wnd.colorBar.max_val=1.0
            self.wnd.colorBar.min_val=0.0        
        
        self.current_dir=os.path.dirname(str(newlist[0]))
        rejected=''
        
        self.progress.setMaximum(len(newlist))
        self.lock()
        self.statusBar.showMessage(tr('Analyzing images, please wait...'))
        count=0
        warnings=False
        listitemslist=[]
        for i in newlist:
            count+=1
            if not (i in self.framelist): #TODO:fix here: string must be compared to string
                page = 0
                img=utils.Frame(str(i),page, **self.frame_open_args)
                if not img.is_good:
                    msgBox = Qt.QMessageBox(self.wnd)
                    msgBox.setText(tr("Cannot open image")+" \""+str(i)+"\"")
                    msgBox.setIcon(Qt.QMessageBox.Critical)
                    msgBox.exec_()
                    continue
                
                while img.is_good:
                    if (imw,imh)!=(img.width,img.height):
                        warnings=True
                        rejected+=(img.url+tr(' --> size does not match:')+'\n'+
                                            tr('current size=')+
                                            str(self.currentWidth)+'x'+str(self.currentHeight)+
                                            ' '+tr('image size=')+
                                            str(img.width)+'x'+str(img.height)+'\n')
                    elif not(dep in img.mode):
                        warnings=True
                        rejected+=(img.url+tr(' --> number of channels does not match:')+'\n'+
                                            tr('current channels=')+
                                            str(self.currentDepht)+
                                            ' '+tr('image channels=')+
                                            str(img.mode)+'\n')
                    else:                    
                        q=Qt.QListWidgetItem(img.tool_name)
                        q.setCheckState(2)
                        q.exif_properties=img.properties
                        q.setToolTip(img.long_tool_name)
                        listitemslist.append(q)
                        img.addProperty('listItem',q)
                        self.framelist.append(img)
                    page+=1
                    img=utils.Frame(str(i),page,  **self.frame_open_args)
                    
            self.progress.setValue(count)
            if self.progressWasCanceled():
                self.framelist=oldlist
                return False
        self.unlock()
        
        for item in listitemslist:
            self.wnd.listWidget.addItem(item)
            
        newlist=[]

        if warnings:
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Some imagese have different sizes or number of channels and will been ignored.\n"))
            msgBox.setInformativeText(tr("All images must have the same size and number of channels.\n\n")+
                                      tr("Click the \'Show Details' button for more information.\n"))
            msgBox.setDetailedText (rejected)
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
            del msgBox

        self.wnd.manualAlignGroupBox.setEnabled(True)
        
        self.darkframelist=[]

        if self.checked_seach_dark_flat==2:
            self.dark_dir = os.path.join(self.current_dir,'dark')
            self.statusBar.showMessage(tr('Searching for dark frames, please wait...'))
            if not self.addDarkFiles(self.dark_dir, ignoreErrors=True):
                pass

            self.flat_dir = os.path.join(self.current_dir,'flat')
            self.statusBar.showMessage(tr('Searching for flatfiled frames, please wait...'))
            if not self.addFlatFiles(self.flat_dir, ignoreErrors=True):
                pass

        self.statusBar.showMessage(tr('DONE'))
        
        if (len(self.framelist)>0):
            self._unlock_cap_ctrls()

        self.statusBar.showMessage(tr('Ready'))

    def doAddBiasFiles(self, clicked):
        self.addBiasFiles()

    def doAddDarkFiles(self, clicked):
        self.addDarkFiles()
        
    def doAddFlatFiles(self, clicked):
        self.addFlatFiles()
        
    def addBiasFiles(self, directory=None, ignoreErrors=False):
        self.addFrameFiles(self.wnd.biasListWidget,
                           self.biasframelist,
                           self.wnd.biasClearPushButton,
                           directory=directory,
                           ignoreErrors=ignoreErrors)
        
    def addDarkFiles(self, directory=None, ignoreErrors=False):
        self.addFrameFiles(self.wnd.darkListWidget,
                           self.darkframelist,
                           self.wnd.darkClearPushButton,
                           directory=directory,
                           ignoreErrors=ignoreErrors)
        
    def addFlatFiles(self, directory=None, ignoreErrors=False):
        self.addFrameFiles(self.wnd.flatListWidget,
                           self.flatframelist,
                           self.wnd.flatClearPushButton,
                           directory=directory,
                           ignoreErrors=ignoreErrors)

    def doClearBiasList(self):
        self.doClearFrameList(self.wnd.biasListWidget,
                              self.biasframelist,
                              self.wnd.biasClearPushButton)

    def doClearDarkList(self):
        self.doClearFrameList(self.wnd.darkListWidget,
                              self.darkframelist,
                              self.wnd.darkClearPushButton)

    def doClearFlatList(self):
        self.doClearFrameList(self.wnd.flatListWidget,
                              self.flatframelist,
                              self.wnd.flatClearPushButton)

    def doClearFrameList(self, framelistwidget, framelist, clearbutton):
        # foce memory release
        while len(framelist) > 0:
            i = framelist.pop()
            del i
        framelistwidget.clear()
        clearbutton.setEnabled(False)

    def addFrameFiles(self, framelistwidget, framelist, clearbutton, directory=None, ignoreErrors=False):
        if directory is None:
            open_str=tr("All supported images")+self.images_extensions+";;"+tr("All files *.* (*.*)")
            files = list(Qt.QFileDialog.getOpenFileNames(self.wnd,
                                                         tr("Select one or more files"),
                                                         self.current_dir,
                                                         open_str,
                                                         None,
                                                         self._dialog_options)
                        )
        elif os.path.exists(directory) and os.path.isdir(directory):
            files = []
            lst = os.listdir(directory)
            for x in lst:
                files.append(os.path.join(directory,x))
        else:
            return False
            
        self.progress.setMaximum(len(files))
        self.lock()
        count=0
        warnings = False
        rejected = ""
        
        for fn in files:

            self.qapp.processEvents()
            self.progress.setValue(count)
            
            
            if (os.path.isfile(str(fn))): #TODO: check for duplicates

               page=0
               i=utils.Frame(str(fn),page, **self.frame_open_args)
               if not i.is_good:
                    if not ignoreErrors:
                        msgBox = Qt.QMessageBox(self.wnd)
                        msgBox.setText(tr("Cannot open image")+" \""+str(fn)+"\"")
                        msgBox.setIcon(Qt.QMessageBox.Critical)
                        msgBox.exec_()
                    continue
               while i.is_good:
                   if ((self.currentWidth == i.width) and
                       (self.currentHeight == i.height) and
                       (self.currentDepht == i.mode)):
                       framelist.append(i)
                       q=Qt.QListWidgetItem(i.tool_name,framelistwidget)
                       q.setToolTip(i.long_tool_name)
                   else:
                        warnings=True
                        rejected+=(i.url+"\n")
                        break
                   page+=1
                   i=utils.Frame(str(fn),page, **self.frame_open_args)

            if self.progressWasCanceled():
                return False
            count+=1
            
        self.unlock()
        
        if warnings:
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Some imagese have different sizes or number of channels and will been ignored.\n"))
            msgBox.setInformativeText(tr("All images must have the same size and number of channels.\n\n")+
                                      tr("Click the \'Show Details' button for more information.\n"))
            msgBox.setDetailedText (rejected)
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
            del msgBox
        
        if (len(framelist) == 0):
            return False
        else:
            clearbutton.setEnabled(True)
        return True

    def clearList(self):
        self.framelist=[]
            
        self.wnd.listWidget.clear()
        self.clearExifTable()
        self.wnd.alignPointsListWidget.clear()
        self.wnd.remPushButton.setEnabled(False)
        self.wnd.clrPushButton.setEnabled(False)
        self.wnd.listCheckAllBtn.setEnabled(False)
        self.wnd.listUncheckAllBtn.setEnabled(False)
        self.wnd.avrPushButton.setEnabled(False)
        self.wnd.alignPushButton.setEnabled(False)
        self.wnd.saveVideoPushButton.setEnabled(False)
        self.wnd.genADUPushButton.setEnabled(False)
        self.deactivateResultControls()
        self.wnd.rawGroupBox.setChecked(False)
        self.wnd.rawGroupBox.setEnabled(False)
        self.clearResult()

    def removeImage(self, clicked):
        q = self.wnd.listWidget.takeItem(self.wnd.listWidget.currentRow())
        self.framelist.pop(self.wnd.listWidget.currentRow())
        del q
        
        self.clearResult()

        if (len(self.framelist)==0):
            self.clearList()
        elif self.image_idx >= len(self.framelist):
            self.wnd.listWidget.setCurrentRow(len(self.framelist)-1)
            self.listItemChanged(self.wnd.listWidget.currentRow())

    def checkAllListItems(self):
        self.setAllListItemsCheckState(2)

    def uncheckAllListItems(self):
        self.setAllListItemsCheckState(0)
        
    def clearDarkList(self):
        self.darkframelist = []
        self.aligned_dark=[]
        
    def clearAlignPoinList(self):
        for frm in self.framelist:
           frm.alignpoints=[]
        self.wnd.alignPointsListWidget.clear()
        self.wnd.removePointPushButton.setEnabled(False)
        self.updateImage()
        
    def clearStarsList(self):
        self.starslist=[]
        self.wnd.starsListWidget.clear()
        self.wnd.removeStarPushButton.setEnabled(False)
        self.updateImage()

    def setAllListItemsCheckState(self, state):
        for i in range(self.wnd.listWidget.count()):
            self.wnd.listWidget.item(i).setCheckState(state)

    def isBayerUsed(self):
        if (self.currentDepht == 'L') and self.wnd.rawGroupBox.isChecked():
            return True
        else:
            return False

    def debayerize(self, data):
        if not(data is None) and (len(data.shape)==2) and self.isBayerUsed():
            
            bayer = self.wnd.bayerComboBox.currentIndex()
            
            correction_factors=[1.0,1.0,1.0]
            
            #NOTE: Cv2 uses BRG images, so we must us the
            #complementery bayer matrix type for example if
            #you want to convert form a RGGB matrix, the
            #BGGR model (BR2RGB) must be used.
            
            if bayer == 0:
                mode = cv2.cv.CV_BayerBG2RGB
            elif bayer == 1:
                mode = cv2.cv.CV_BayerGB2RGB
            elif bayer == 2:
                mode = cv2.cv.CV_BayerRG2RGB
            else: # this shuold be only bayer == 3
                mode = cv2.cv.CV_BayerGR2RGB
            
            #TODO: Create a native debayerizing algorithm
            
            new_data=cv2.cvtColor((data-data.min()).astype(np.uint16),mode).astype(self.ftype)*correction_factors
            
            return new_data
        else:
            return data

    def updateBayerMatrix(self, *arg):
        # we are forced to ignore *arg because this
        # function is connected  to multiple signals
        if len(self.framelist) == 0:
            return
        
        self.updateBayerComponents()
        
        img = self.framelist[self.image_idx]
        arr = self.debayerize(img.getData(asarray=True))
        
        if self.wnd.rawGroupBox.isChecked():
            self.wnd.colorBar._is_rgb=True
        else:
            self.wnd.colorBar._is_rgb = img.isRGB()
        
        
        qimg=utils.arrayToQImage(arr,bw_jet=self.use_colormap_jet,fit_levels=self.fit_levels,levels_range=self.levels_range)
        self.showImage(qimg)
        
    
    def clearExifTable(self):
        self.wnd.exifTableWidget.clearContents()
        self.wnd.exifTableWidget.setRowCount(0)
    
    def updateADUlistItemChanged(self, idx):
        
        if idx < 0:
            self.wnd.pointsADUComboBox.setEnabled(False)
            self.wnd.lineADUComboBox.setEnabled(False)
            self.wnd.barsADUComboBox.setEnabled(False)
            self.wnd.colorADUComboBox.setEnabled(False)
            self.wnd.smoothingADUDoubleSpinBox.setEnabled(False)
            self.wnd.smoothingADUDoubleSpinBox.setEnabled(False)
            self.wnd.pointSizeADUDoubleSpinBox.setEnabled(False)
            self.wnd.lineWidthADUDoubleSpinBox.setEnabled(False)
            return False
        else:
            self.wnd.pointsADUComboBox.setEnabled(True)
            self.wnd.lineADUComboBox.setEnabled(True)
            self.wnd.barsADUComboBox.setEnabled(True)
            self.wnd.colorADUComboBox.setEnabled(True)
            self.wnd.smoothingADUDoubleSpinBox.setEnabled(True)
            self.wnd.pointSizeADUDoubleSpinBox.setEnabled(True)
            self.wnd.lineWidthADUDoubleSpinBox.setEnabled(True)
        
        q = self.wnd.aduListWidget.item(idx)
        self.wnd.colorADUComboBox.setCurrentIndex(self.getChartColorIndex(q.chart_properties['color'])) 
        
        pointstype=q.chart_properties['points']
        linetype=q.chart_properties['line']
        barstype=q.chart_properties['bars']
        smoothing=q.chart_properties['smoothing']
        pointsize=q.chart_properties['point_size']
        linewidth=q.chart_properties['line_width']
        
        try:
            pnt_index=utils.POINTS_TYPE.index(pointstype)
            self.wnd.pointsADUComboBox.setCurrentIndex(pnt_index)
        except:
            self.wnd.pointsADUComboBox.setCurrentIndex(1)
            
        try:
            ln_index=utils.LINES_TYPE.index(linetype)
            self.wnd.lineADUComboBox.setCurrentIndex(ln_index)
        except:
            self.wnd.lineADUComboBox.setCurrentIndex(0)

        try:
            bar_index=utils.BARS_TYPE.index(barstype)
            self.wnd.barsADUComboBox.setCurrentIndex(bar_index)
        except:
            self.wnd.barsADUComboBox.setCurrentIndex(1)
        
    
        self.wnd.smoothingADUDoubleSpinBox.setValue(smoothing)
        self.wnd.pointSizeADUDoubleSpinBox.setValue(pointsize)
        self.wnd.lineWidthADUDoubleSpinBox.setValue(linewidth)
        

    def updateMaglistItemChanged(self, idx):
        
        if idx < 0:
            self.wnd.pointsMagComboBox.setEnabled(False)
            self.wnd.lineMagComboBox.setEnabled(False)
            self.wnd.barsMagComboBox.setEnabled(False)
            self.wnd.colorMagComboBox.setEnabled(False)
            self.wnd.smoothingMagDoubleSpinBox.setEnabled(False)
            self.wnd.pointSizeMagDoubleSpinBox.setEnabled(False)
            self.wnd.lineWidthMagDoubleSpinBox.setEnabled(False)
            return False
        else:
            self.wnd.pointsMagComboBox.setEnabled(True)
            self.wnd.lineMagComboBox.setEnabled(True)
            self.wnd.barsMagComboBox.setEnabled(True)
            self.wnd.colorMagComboBox.setEnabled(True)
            self.wnd.smoothingMagDoubleSpinBox.setEnabled(True)
            self.wnd.pointSizeMagDoubleSpinBox.setEnabled(True)
            self.wnd.lineWidthMagDoubleSpinBox.setEnabled(True)
        
        q = self.wnd.magListWidget.item(idx)
        self.wnd.colorMagComboBox.setCurrentIndex(self.getChartColorIndex(q.chart_properties['color'])) 
        
        pointstype=q.chart_properties['points']
        linetype=q.chart_properties['line']
        barstype=q.chart_properties['bars']
        smoothing=q.chart_properties['smoothing']
        pointsize=q.chart_properties['point_size']
        linewidth=q.chart_properties['line_width']
                
        try:
            pnt_index=utils.POINTS_TYPE.index(pointstype)
            self.wnd.pointsMagComboBox.setCurrentIndex(pnt_index)
        except:
            self.wnd.pointsMagComboBox.setCurrentIndex(1)
            
        try:
            ln_index=utils.LINES_TYPE.index(linetype)
            self.wnd.lineMagComboBox.setCurrentIndex(ln_index)
        except:
            self.wnd.lineMagComboBox.setCurrentIndex(0)

        try:
            bar_index=utils.BARS_TYPE.index(barstype)
            self.wnd.barsMagComboBox.setCurrentIndex(bar_index)
        except:
            self.wnd.barsMagComboBox.setCurrentIndex(1)
    
        self.wnd.smoothingMagDoubleSpinBox.setValue(smoothing)
        self.wnd.pointSizeMagDoubleSpinBox.setValue(pointsize)
        self.wnd.lineWidthMagDoubleSpinBox.setValue(linewidth)
    
    def listItemChanged(self, idx):
        if self.wasStarted:
            return
        self.qapp.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.image_idx = self.wnd.listWidget.currentRow()
        
        if idx >= 0:
            img = self.framelist[idx]
            qimg=utils.arrayToQImage(self.debayerize(img.getData(asarray=True)),
                                     bw_jet=self.use_colormap_jet,
                                     fit_levels=self.fit_levels,
                                     levels_range=self.levels_range)
            self.showImage(qimg)
            
            self.wnd.alignGroupBox.setEnabled(True)
            self.wnd.alignDeleteAllPushButton.setEnabled(True)
            self.updateAlignPointList()
            self.wnd.manualAlignGroupBox.setEnabled(True)

            try:            
                props=self.wnd.listWidget.currentItem().exif_properties
            except:
                pass
            else:            
                self.clearExifTable()
                self.wnd.exifTableWidget.setSortingEnabled(False) # See Qt doc to undertand why this is needed
                for k,v in props.items():
                    if type(v) != Qt.QListWidgetItem:
                        self.wnd.exifTableWidget.insertRow(0)
                        key_item=Qt.QTableWidgetItem(str(k))
                        value_item=Qt.QTableWidgetItem(str(v))
                        self.wnd.exifTableWidget.setItem(0,0,key_item)
                        self.wnd.exifTableWidget.setItem(0,1,value_item)
                self.wnd.exifTableWidget.setSortingEnabled(True)    
        else:
            self.clearImage()
            self.wnd.alignGroupBox.setEnabled(False)
            self.wnd.alignDeleteAllPushButton.setEnabled(False)
            self.wnd.manualAlignGroupBox.setEnabled(False)
            
        self.wnd.colorBar.repaint()
        self.qapp.restoreOverrideCursor()
        
    def manualAlignListItemChanged(self,idx):
        item = self.wnd.listWidgetManualAlign.item(idx)
        if item is None:
            return        
        self.dif_image_idx=item.original_id
        img = self.framelist[item.original_id]
        self.qapp.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.current_image=utils.arrayToQImage(img.getData(asarray=True),
                                               bw_jet=self.use_colormap_jet,
                                               fit_levels=self.fit_levels,
                                               levels_range=self.levels_range)
        self.wnd.doubleSpinBoxOffsetX.setValue(img.offset[0])
        self.wnd.doubleSpinBoxOffsetY.setValue(img.offset[1])
        self.wnd.spinBoxOffsetT.setValue(img.angle)
        self.updateImage()
        self.qapp.restoreOverrideCursor()

    def currentManualAlignListItemChanged(self, cur_item):
        if cur_item is None:
            return False
        elif cur_item.checkState()==2:
            if self.__operating!=True:
                self.__operating=True
                self.ref_image_idx=cur_item.original_id
                #self.ref_image = Qt.QImage(self.framelist[cur_item.original_id])
                img = self.framelist[cur_item.original_id]
                self.ref_image=utils.arrayToQImage(img.getData(asarray=True),
                                                   bw_jet=self.use_colormap_jet,
                                                   fit_levels=self.fit_levels,
                                                   levels_range=self.levels_range)
                for i in range(self.wnd.listWidgetManualAlign.count()):
                    item = self.wnd.listWidgetManualAlign.item(i)
                    if (item != cur_item) and (item.checkState() == 2):
                        item.setCheckState(0)
                self.__operating=False
                self.imageLabel.repaint()
        elif cur_item.checkState()==0:
            if not self.__operating:
                cur_item.setCheckState(2)


            
    def updateAlignList(self):
        if self.ref_image_idx == -1:
            self.ref_image_idx=0
        self.wnd.listWidgetManualAlign.clear()
        count=0
        self.__operating=True
        for i in range(self.wnd.listWidget.count()):
            if self.wnd.listWidget.item(i).checkState()==2:
                item = self.wnd.listWidget.item(i)
                if item.checkState()==2:
                    q=Qt.QListWidgetItem(item.text(),self.wnd.listWidgetManualAlign)
                    q.original_id=i
                    if i == self.ref_image_idx:
                        q.setCheckState(2)
                    else:
                        q.setCheckState(0)
                    count+=1
        self.__operating=False

    def alignListItemChanged(self, idx):
        self.point_idx=idx
        if idx >= 0:
            self.wnd.spinBoxXAlign.setEnabled(True)
            self.wnd.spinBoxYAlign.setEnabled(True)
            self.wnd.removePointPushButton.setEnabled(True)
            pnt=self.framelist[self.image_idx].alignpoints[idx]
            self.wnd.spinBoxXAlign.setValue(pnt[0])
            self.wnd.spinBoxYAlign.setValue(pnt[1])
        else:
            self.wnd.spinBoxXAlign.setEnabled(False)
            self.wnd.spinBoxYAlign.setEnabled(False)
            self.wnd.removePointPushButton.setEnabled(False)
            self.wnd.spinBoxXAlign.setValue(0)
            self.wnd.spinBoxYAlign.setValue(0)

    def starsListItemChanged(self,q):
        if q.checkState()==0:
            self.starslist[q.original_id][6]=False
            self.wnd.magDoubleSpinBox.setEnabled(False)
        else:
            self.starslist[q.original_id][6]=True
            self.wnd.magDoubleSpinBox.setEnabled(True)
        
        self.updateImage()
        
    def currentStarsListItemChanged(self, idx):
        self.star_idx=idx

        if idx >= 0:
            self.wnd.spinBoxXStar.setEnabled(True)
            self.wnd.spinBoxYStar.setEnabled(True)
            self.wnd.innerRadiusDoubleSpinBox.setEnabled(True)
            self.wnd.middleRadiusDoubleSpinBox.setEnabled(True)
            self.wnd.outerRadiusDoubleSpinBox.setEnabled(True)
            self.wnd.magDoubleSpinBox.setEnabled(True)
            self.wnd.removeStarPushButton.setEnabled(True)
            pnt=self.starslist[idx]
            
            if pnt[6]==True:
                self.wnd.magDoubleSpinBox.setEnabled(True)
            else:
                self.wnd.magDoubleSpinBox.setEnabled(False)
                
            self.wnd.spinBoxXStar.setValue(pnt[0])
            self.wnd.spinBoxYStar.setValue(pnt[1])
            self.wnd.innerRadiusDoubleSpinBox.setValue(pnt[3])
            self.wnd.middleRadiusDoubleSpinBox.setValue(pnt[4])
            self.wnd.outerRadiusDoubleSpinBox.setValue(pnt[5])
            self.wnd.magDoubleSpinBox.setValue(pnt[7])
        else:
            self.wnd.spinBoxXStar.setEnabled(False)
            self.wnd.spinBoxYStar.setEnabled(False)
            self.wnd.innerRadiusDoubleSpinBox.setEnabled(False)
            self.wnd.middleRadiusDoubleSpinBox.setEnabled(False)
            self.wnd.outerRadiusDoubleSpinBox.setEnabled(False)
            self.wnd.removeStarPushButton.setEnabled(False)
            self.wnd.magDoubleSpinBox.setEnabled(False)
            self.wnd.spinBoxXStar.setValue(0)
            self.wnd.spinBoxYStar.setValue(0)
            self.wnd.innerRadiusDoubleSpinBox.setValue(0)
            self.wnd.middleRadiusDoubleSpinBox.setValue(0)
            self.wnd.outerRadiusDoubleSpinBox.setValue(0)
            self.wnd.magDoubleSpinBox.setValue(0)
            
    def addAlignPoint(self):
        
        if self.dlg.autoSizeCheckBox.checkState()==2:
            r_w=int(self.currentWidth/10)
            r_h=int(self.currentHeight/10)
            r_l=max(r_w,r_h)
            self.autoalign_rectangle=(r_l,r_h)
            self.dlg.rWSpinBox.setValue(r_l)
            self.dlg.rHSpinBox.setValue(r_l)
        
        imagename=self.wnd.listWidget.item(self.image_idx).text()
        idx=1
        for i in range(self.wnd.alignPointsListWidget.count()):
            pname='#{0:05d}'.format(i+1)
            if self.framelist[0].alignpoints[i][2] != pname:
                idx=i+1
                break
            else:
                idx=i+2
                
        pname='#{0:05d}'.format(idx)
        q=Qt.QListWidgetItem(pname)
        q.setToolTip(tr('image') +imagename+tr('\nalign point ')+pname)
        self.wnd.alignPointsListWidget.insertItem(idx-1,q)
        
        if(len(self.framelist[self.image_idx].alignpoints)==0):
            self.wnd.removePointPushButton.setEnabled(False)
            
        for frm in self.framelist:
           frm.alignpoints.insert(idx-1,[0,0,pname,False])

        self.imageLabel.repaint()
        self.wnd.alignPointsListWidget.setCurrentRow(idx-1)
        return (idx-1)
    
    def addStar(self):
                
        idx=1
        for i in range(self.wnd.starsListWidget.count()):
            pname='star#{0:05d}'.format(i+1)
            if self.starslist[i][2] != pname:
                idx=i+1
                break
            else:
                idx=i+2
                
        pname='star#{0:05d}'.format(idx)
        q=Qt.QListWidgetItem(pname)
        q.setCheckState(0)
        q.original_id=idx-1
        self.wnd.starsListWidget.insertItem(idx-1,q)
        
        if(len(self.starslist)==0):
            self.wnd.removeStarPushButton.setEnabled(False)
        
        self.starslist.insert(idx-1,[0,0,pname,7,10,15,False,0])
        
        self.imageLabel.repaint()
        self.wnd.starsListWidget.setCurrentRow(idx-1)
        return (idx-1)
    
    
    def removeAlignPoint(self):
        
        point_idx=self.wnd.alignPointsListWidget.currentRow()
        
        for frm in self.framelist:
            frm.alignpoints.pop(point_idx)
            
        self.wnd.alignPointsListWidget.setCurrentRow(-1) #needed to avid bugs
        item = self.wnd.alignPointsListWidget.takeItem(point_idx)
        
        if(len(self.framelist[self.image_idx].alignpoints)==0):
            self.wnd.removePointPushButton.setEnabled(False)
            
        del item
        
        self.updateImage()

    def removeStar(self):
        
        star_idx=self.wnd.starsListWidget.currentRow()
        
        self.starslist.pop(star_idx)
            
        self.wnd.starsListWidget.setCurrentRow(-1) #needed to avid bugs
        item = self.wnd.starsListWidget.takeItem(star_idx)
        
        if(len(self.starslist)==0):
            self.wnd.removePointPushButton.setEnabled(False)
            
        del item
        
        self.updateImage()

        
    def updateAlignPointList(self):
        self.wnd.alignPointsListWidget.clear()
        imagename=self.wnd.listWidget.item(self.wnd.listWidget.currentRow()).text()
        for pnt in self.framelist[self.image_idx].alignpoints:
            pname=pnt[2]
            q=Qt.QListWidgetItem(pname,self.wnd.alignPointsListWidget)
            q.setToolTip(tr('image') +imagename+tr('\nalign point ')+pname)

    def shiftX(self,val):
        if (self.point_idx >= 0):
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt[0]=val
            if pnt[3]==True:
                pnt[3]=False
            self.imageLabel.repaint()

    def shiftY(self,val):
        if (self.point_idx >= 0):
            pnt = self.framelist[self.image_idx].alignpoints[self.point_idx]
            pnt[1]=val
            if pnt[3]==True:
                pnt[3]=False
            self.imageLabel.repaint()
            
    
    def shiftStarX(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt[0]=val
            self.imageLabel.repaint()
            
    def shiftStarY(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt[1]=val
            self.imageLabel.repaint()
            
    def setInnerRadius(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt[3]=val
            if (pnt[4]-pnt[3] < 2):
                self.wnd.middleRadiusDoubleSpinBox.setValue(pnt[3]+2)
            self.imageLabel.repaint()
            
    def setMiddleRadius(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt[4]=val
            if (pnt[4]-pnt[3] < 2):
                self.wnd.innerRadiusDoubleSpinBox.setValue(pnt[4]-2)
            if (pnt[5]-pnt[4] < 2):
                self.wnd.outerRadiusDoubleSpinBox.setValue(pnt[4]+2)
            self.imageLabel.repaint()
            
    def setOuterRadius(self,val):
        if (self.star_idx >= 0):
            pnt = self.starslist[self.star_idx]
            pnt[5]=val
            if (pnt[5]-pnt[4] < 2):
                self.wnd.middleRadiusDoubleSpinBox.setValue(pnt[5]-2)
            self.imageLabel.repaint()
    
    def setMagnitude(self,val):
        self.starslist[self.star_idx][7]=val
    
    def shiftOffsetX(self,val):
        if (self.dif_image_idx >= 0):
            self.framelist[self.dif_image_idx].offset[0]=val
            self.imageLabel.repaint()
    
    def shiftOffsetY(self,val):
        if (self.dif_image_idx >= 0):
            self.framelist[self.dif_image_idx].offset[1]=val
            self.imageLabel.repaint()
    
    def rotateOffsetT(self, val):
        if (self.dif_image_idx >= 0):
            self.framelist[self.dif_image_idx].angle=val
            self.imageLabel.repaint()
    
    def updateToolBox(self, idx):
        self.ref_image_idx=-1
        self.qapp.setOverrideCursor(QtCore.Qt.WaitCursor)
        if (idx<=1) and  (self._old_tab_idx==7) or (self._old_tab_idx==2):
            try:
                if self.image_idx>=0:
                    img = self.framelist[self.image_idx]
                    qimg=utils.arrayToQImage(self.debayerize(img.getData(asarray=True)),
                                             bw_jet=self.use_colormap_jet,
                                             fit_levels=self.fit_levels,
                                             levels_range=self.levels_range)
                    self.showImage(qimg)
            except IndexError:
                pass #maybe there are no images in the list yet?

        self.showAlignPoints=False
        self.showStarPoints=False
        
        if (idx==1) or (idx==6):
            self.use_cursor = QtCore.Qt.CrossCursor
            self.wnd.imageViewer.setCursor(QtCore.Qt.CrossCursor)
            self.imageLabel.setCursor(QtCore.Qt.CrossCursor)
        else:
            self.use_cursor = QtCore.Qt.OpenHandCursor
            self.wnd.imageViewer.setCursor(QtCore.Qt.OpenHandCursor)
            self.imageLabel.setCursor(QtCore.Qt.OpenHandCursor)
        
        if idx==0:
            self.showStarPoints=True
        
        if idx==1:
            self.showAlignPoints=True
                    
        if idx==2:
            self.trace("Setting up manual alignment controls")
            self.manual_align=True
            self.trace("Updating list of available images")
            self.updateAlignList()
            if self.wnd.listWidgetManualAlign.count()>0:
                img=self.framelist[self.wnd.listWidgetManualAlign.item(0).original_id]
                self.trace("Loading reference image")
                self.ref_image = utils.arrayToQImage(img.getData(asarray=True),
                                                     bw_jet=self.use_colormap_jet,
                                                     fit_levels=self.fit_levels,
                                                     levels_range=self.levels_range)
                self.trace("Selecting reference image")
                self.wnd.listWidgetManualAlign.setCurrentRow(0)
                self.updateImage()
        else:
            self.manual_align=False
            
        if (idx==6):
            self.showStarPoints=True
            try:
                if self.image_idx>=0:
                    # the first enabled frame must be used
                    for i in range(len(self.framelist)):
                        if self.framelist[i].isUsed():
                            self.image_idx=i
                            break
                    self.wnd.listWidget.setCurrentRow(self.image_idx)
                    img = self.framelist[self.image_idx]
                    qimg=utils.arrayToQImage(self.debayerize(img.getData(asarray=True)),
                                             bw_jet=self.use_colormap_jet,
                                             fit_levels=self.fit_levels,
                                             levels_range=self.levels_range)
                    self.showImage(qimg)
            except IndexError:
                pass #maybe there are no images in the list yet?             
        
            
        if (idx==7):
            self.updateResultImage()
            if (len(self.framelist)>0):
                self.wnd.alignPushButton.setEnabled(True)
                self.wnd.avrPushButton.setEnabled(True)
                self.wnd.saveVideoPushButton.setEnabled(True)
                self.wnd.genADUPushButton.setEnabled(True)

        self.imageLabel.repaint()
        self._old_tab_idx=idx
        self.qapp.restoreOverrideCursor()
        
    def newProject(self):
                
        self.wnd.toolBox.setCurrentIndex(0)
        self.wnd.captureGroupBox.setChecked(False)
        self.wnd.bayerComboBox.setCurrentIndex(0)
        
        self.wnd.setWindowTitle(str(paths.PROGRAM_NAME)+' [Untitled Project]')
        
        self.zoom = 1
        self.min_zoom = 0
        self.actual_zoom=1
        self.exposure=0
        self.zoom_enabled=False
        self.zoom_fit=False
        self.current_image = None
        self.ref_image=None

        self.image_idx=-1
        self.ref_image_idx=-1
        self.dif_image_idx=-1
        self.point_idx=-1
        self.star_idx=-1

        self.clearResult()
    
        self.manual_align=False

        self.currentWidth=0
        self.currentHeight=0
        self.currentDepht=0
        
        self.result_w=0
        self.result_h=0
        self.result_d=3
        
        self.current_project_fname=None

        del self.framelist
        del self.biasframelist
        del self.darkframelist
        del self.flatframelist

        del self.master_bias_file
        del self.master_dark_file
        del self.master_flat_file
        
        self.master_bias_file=None
        self.master_dark_file=None
        self.master_flat_file=None

        self.framelist=[]
        self.biasframelist=[]     
        self.darkframelist=[]
        self.flatframelist=[]
        self.starslist=[]
        self.lightcurve={}
        
        self.wnd.chartsTabWidget.setTabEnabled(1,False)
        self.wnd.chartsTabWidget.setTabEnabled(2,False)
        
        self.setZoom(1)
        self.setZoomMode(1,True)
        self.wnd.alignPushButton.setEnabled(False)
        self.wnd.avrPushButton.setEnabled(False)
        self.deactivateResultControls()
        self.wnd.alignGroupBox.setEnabled(False)
        self.wnd.manualAlignGroupBox.setEnabled(False)
        self.wnd.masterBiasGroupBox.setEnabled(False)
        self.wnd.masterDarkGroupBox.setEnabled(False)
        self.wnd.masterFlatGroupBox.setEnabled(False)
        self.wnd.biasFramesGroupBox.setEnabled(True)
        self.wnd.darkFramesGroupBox.setEnabled(True)
        self.wnd.flatFramesGroupBox.setEnabled(True)
        self.wnd.saveADUChartPushButton.setEnabled(False)
        self.wnd.saveMagChartPushButton.setEnabled(False)
        self.wnd.masterDarkGroupBox.hide()
        self.wnd.masterFlatGroupBox.hide()
        self.wnd.masterBiasGroupBox.hide()
        self.wnd.flatFramesGroupBox.show()
        self.wnd.darkFramesGroupBox.show()
        self.wnd.biasFramesGroupBox.show()
        self.wnd.masterBiasCheckBox.setCheckState(0)
        self.wnd.masterDarkCheckBox.setCheckState(0)
        self.wnd.masterFlatCheckBox.setCheckState(0)
        self.wnd.biasMulDoubleSpinBox.setValue(1.0)
        self.wnd.darkMulDoubleSpinBox.setValue(1.0)
        self.wnd.flatMulDoubleSpinBox.setValue(1.0)
        self.wnd.fitMinMaxCheckBox.setCheckState(0)
        self.clearList()
        self.wnd.biasListWidget.clear()
        self.wnd.darkListWidget.clear()
        self.wnd.flatListWidget.clear()
        self.wnd.starsListWidget.clear()
        self.wnd.aduListWidget.clear()
        self.wnd.magListWidget.clear()
        self.wnd.masterBiasLineEdit.setText('')
        self.wnd.masterDarkLineEdit.setText('')
        self.wnd.masterFlatLineEdit.setText('')
        self.progress.reset()
        self.clearImage()
        self.clearExifTable()
        
        self.setLevelsRange((0,100))
        self.setDisplayLevelsFitMode(0)
        
        self.clearComponents()
        
    def saveProjectAs(self):
        self.current_project_fname = str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the project"),
                                         os.path.join(self.current_dir,'Untitled.lxn'),
                                         "Project (*.lxn);;All files (*.*)", None,
                                         self._dialog_options))
        if self.current_project_fname == '':
            self.current_project_fname=None
            return
        self._save_project()

    def saveProject(self):
        if self.current_project_fname is None:
            self.saveProjectAs()
        else:
            self._save_project()

    def corruptedMsgBox(self,info=None):
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("The project is invalid or corrupted!"))
            if not(info is None):
                msgBox.setInformativeText(str(info))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            return False

    def _save_project(self):
        
        self.lock(False)
        self.progress.reset()
        self.statusBar.showMessage(tr('saving project, please wait...'))
        
        if self.wnd.rawGroupBox.isChecked():
            bayer_mode=self.wnd.bayerComboBox.currentIndex()
        else:
            bayer_mode=-1
        
        doc = minidom.Document()
        
        root=doc.createElement('project')
        doc.appendChild(root)
        
        information_node = doc.createElement('information')
        bias_frames_node = doc.createElement('bias-frames')
        dark_frames_node = doc.createElement('dark-frames')
        flat_frames_node = doc.createElement('flat-frames')
        pict_frames_node = doc.createElement('frames')
        photometry_node = doc.createElement('photometry')

        root.appendChild(information_node)
        root.appendChild(bias_frames_node)
        root.appendChild(dark_frames_node)
        root.appendChild(flat_frames_node)
        root.appendChild(pict_frames_node)
        root.appendChild(photometry_node)
        
        #<information> section
        information_node.setAttribute('width',str(int(self.currentWidth)))
        information_node.setAttribute('height',str(int(self.currentHeight)))
        information_node.setAttribute('mode',str(self.currentDepht))
        information_node.setAttribute('bayer-mode',str(int(bayer_mode)))
        
        current_dir_node = doc.createElement('current-dir')
        current_row_node = doc.createElement('current-row')
        master_bias_node = doc.createElement('master-bias')
        master_dark_node = doc.createElement('master-dark')
        master_flat_node = doc.createElement('master-flat')
        align_rect_node  = doc.createElement('align-rect')
        max_points_node  = doc.createElement('max-align-points')
        min_quality_node = doc.createElement('min-point-quality')
        
        
        information_node.appendChild(current_dir_node)
        information_node.appendChild(current_row_node)
        information_node.appendChild(master_bias_node)
        information_node.appendChild(master_dark_node)
        information_node.appendChild(master_flat_node)
        information_node.appendChild(align_rect_node)
        information_node.appendChild(max_points_node)
        information_node.appendChild(min_quality_node)
        
        current_dir_node.setAttribute('url',str(self.current_dir))
        current_row_node.setAttribute('index',str(self.image_idx))
        master_bias_node.setAttribute('checked',str(self.wnd.masterBiasCheckBox.checkState()))
        master_bias_node.setAttribute('mul',str(self.master_bias_mul_factor))
        master_dark_node.setAttribute('checked',str(self.wnd.masterDarkCheckBox.checkState()))
        master_dark_node.setAttribute('mul',str(self.master_dark_mul_factor))
        master_flat_node.setAttribute('checked',str(self.wnd.masterFlatCheckBox.checkState()))
        master_flat_node.setAttribute('mul',str(self.master_flat_mul_factor))
        align_rect_node.setAttribute('width',str(self.autoalign_rectangle[0]))
        align_rect_node.setAttribute('height',str(self.autoalign_rectangle[1]))
        align_rect_node.setAttribute('whole-image',str(self.auto_align_use_whole_image))
        max_points_node.setAttribute('value',str(self.max_points))
        min_quality_node.setAttribute('value',str(self.min_quality))

        url=doc.createElement('url')
        master_bias_node.appendChild(url)
        url_txt=doc.createTextNode(str(self.wnd.masterBiasLineEdit.text()))
        url.appendChild(url_txt)

        url=doc.createElement('url')
        master_dark_node.appendChild(url)
        url_txt=doc.createTextNode(str(self.wnd.masterDarkLineEdit.text()))
        url.appendChild(url_txt)
        
        url=doc.createElement('url')
        master_flat_node.appendChild(url)
        url_txt=doc.createTextNode(str(self.wnd.masterFlatLineEdit.text()))
        url.appendChild(url_txt)
        
        total_bias = len(self.biasframelist)
        total_dark = len(self.darkframelist)
        total_flat = len(self.flatframelist)
        total_imgs = len(self.framelist)
        total_strs = len(self.starslist)
        
        self.progress.setMaximum(total_bias+total_dark+total_flat+total_imgs+total_strs-1)
        
        count=0
        
        #<bias-frams> section
        for i in self.biasframelist:

            self.progress.setValue(count)
            count+=1
            
            im_bias_name = i.tool_name
            im_bias_url  = i.url
            im_bias_page = i.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_bias_name)
            
            bias_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_bias_url)
            url.appendChild(url_txt)
            url.setAttribute('page',str(im_bias_page))
        
        #<dark-frams> section
        for i in self.darkframelist:

            self.progress.setValue(count)
            count+=1
            
            im_dark_name = i.tool_name
            im_dark_url  = i.url
            im_dark_page = i.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_dark_name)
            
            dark_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_dark_url)
            url.appendChild(url_txt)
            url.setAttribute('page',str(im_dark_page))

        #<flat-frames> section
        for i in self.flatframelist:
            
            self.progress.setValue(count)
            count+=1

            im_flat_name = i.tool_name
            im_flat_url  = i.url
            im_flat_page = i.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_flat_name)
            
            flat_frames_node.appendChild(image_node)
            
            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_flat_url)
            url.appendChild(url_txt)  
            url.setAttribute('page',str(im_flat_page))
            
        #<frames> section
        for img in self.framelist:
            
            self.progress.setValue(count)
            count+=1
            im_used = str(img.isUsed())
            im_name = str(img.tool_name)
            im_url  = img.url
            im_page = img.page
            image_node = doc.createElement('image')
            image_node.setAttribute('name',im_name)
            image_node.setAttribute('used',im_used)
            
            pict_frames_node.appendChild(image_node)

            for point in img.alignpoints:
                point_node=doc.createElement('align-point')
                point_node.setAttribute('x',str(int(point[0])))
                point_node.setAttribute('y',str(int(point[1])))
                point_node.setAttribute('id',str(point[2]))
                point_node.setAttribute('aligned',str(point[3]))
                image_node.appendChild(point_node)
            
            offset_node=doc.createElement('offset')
            offset_node.setAttribute('x',str(float(img.offset[0])))
            offset_node.setAttribute('y',str(float(img.offset[1])))
            offset_node.setAttribute('theta',str(float(img.angle)))
            image_node.appendChild(offset_node)

            url=doc.createElement('url')
            image_node.appendChild(url)
            url_txt=doc.createTextNode(im_url)
            url.appendChild(url_txt)
            url.setAttribute('page',str(im_page))

        #photometry section
        photometry_node.setAttribute('time_type',str(int(self.use_image_time)))
        for i in range(len(self.starslist)):
            s=self.starslist[i]
            self.progress.setValue(count)
            count+=1
            star_node = doc.createElement('star')
            star_node.setAttribute('x',str(int(s[0])))
            star_node.setAttribute('y',str(int(s[1])))
            star_node.setAttribute('name',str(s[2]))
            star_node.setAttribute('inner_radius',str(float(s[3])))
            star_node.setAttribute('middle_radius',str(float(s[4])))
            star_node.setAttribute('outer_radius',str(float(s[5])))
            star_node.setAttribute('reference',str(int(s[6])))
            star_node.setAttribute('magnitude',str(float(s[7])))
            star_node.setAttribute('idx',str(int(i)))
            photometry_node.appendChild(star_node)
            
        try:
            f = open(self.current_project_fname,'w')
            f.write(doc.toprettyxml(' ','\n'))
            f.close()
        except IOError as err:
            self.trace("Cannot save the project: " + str(err))
            msgBox = Qt.QMessageBox(self.wnd)
            msgBox.setText(tr("Cannot save the project: ")+ str(err))
            msgBox.setInformativeText(tr("Assure you have the permissions to write the file."))
            msgBox.setIcon(Qt.QMessageBox.Critical)
            msgBox.exec_()
            del msgBox
            self.unlock()
            return
        
        self.wnd.setWindowTitle(str(paths.PROGRAM_NAME)+' ['+self.current_project_fname+']')
        self.unlock()
    
    def loadProject(self,pname=None):
        
        self.trace('\nloading project, please wait...\n')
        old_fname = self.current_project_fname
        
        if pname is None:
            project_fname = str(Qt.QFileDialog.getOpenFileName(self.wnd,
                                                            tr("Open a project"),
                                                            os.path.join(self.current_dir,'Untitled.lxn'),
                                                            "Project (*.lxn *.prj);;All files (*.*)", None,
                                                            self._dialog_options)
                            )
        else:
            project_fname=pname
            
        if project_fname.replace(' ','') == '':
            self.trace(' no project selected, retvert to previous state\n') 
            return False
        else:
            self.trace(' project name: \''+str(project_fname)+'\'') 
            
        try:
            dom = minidom.parse(project_fname)
        except Exception as err:
            self.trace('failed to parse project, xml formatting error') 
            return self.corruptedMsgBox(err)       

        self.statusBar.showMessage(tr('loading project, please wait...'))
        self.lock(False)

        try:
            root = dom.getElementsByTagName('project')[0]
            
            information_node = root.getElementsByTagName('information')[0]
            dark_frames_node = root.getElementsByTagName('dark-frames')[0]
            flat_frames_node = root.getElementsByTagName('flat-frames')[0]
            pict_frames_node = root.getElementsByTagName('frames')[0]
            
            try: #backward compatibility
                bias_frames_node = root.getElementsByTagName('bias-frames')[0]
                total_bias =len(bias_frames_node.getElementsByTagName('image'))
                master_bias_node = information_node.getElementsByTagName('master-bias')[0]
                master_bias_checked=int(master_bias_node.getAttribute('checked'))
                master_bias_mul_factor=float(master_bias_node.getAttribute('mul'))
                _bias_section=True
            except Exception as exc:
                self.trace('no bias section')
                total_bias=0
                master_bias_node=None
                _bias_section=False
            
            try:
                photometry_node = root.getElementsByTagName('photometry')[0]
                _fotometric_section=True
            except Exception as exc:
                self.trace('no fotometric section, skipping star loading')
                _fotometric_section=False
                                
            total_dark = len(dark_frames_node.getElementsByTagName('image'))
            total_flat = len(flat_frames_node.getElementsByTagName('image'))
            total_imgs =len(pict_frames_node.getElementsByTagName('image'))
            
            self.progress.reset()
            self.progress.setMaximum(total_bias+total_dark+total_flat+total_imgs-1)
            count=0
            
            self.trace('\nloading project information')
            
            current_dir_node = information_node.getElementsByTagName('current-dir')[0]
            current_row_node = information_node.getElementsByTagName('current-row')[0]
            master_dark_node = information_node.getElementsByTagName('master-dark')[0]
            master_flat_node = information_node.getElementsByTagName('master-flat')[0]
            align_rect_node  = information_node.getElementsByTagName('align-rect')[0]
            max_points_node  = information_node.getElementsByTagName('max-align-points')[0]
            min_quality_node = information_node.getElementsByTagName('min-point-quality')[0]

            imw=int(information_node.getAttribute('width'))
            imh=int(information_node.getAttribute('height'))
            dep=information_node.getAttribute('mode')
            
            try:
                bayer_mode=int(information_node.getAttribute('bayer-mode'))
            except:
                bayer_mode=-1
                
            ar_w=int(align_rect_node.getAttribute('width'))
            ar_h=int(align_rect_node.getAttribute('height'))
            use_whole_image=int(align_rect_node.getAttribute('whole-image'))
            max_points=int(max_points_node.getAttribute('value'))
            min_quality=float(min_quality_node.getAttribute('value'))
                        
            current_dir=current_dir_node.getAttribute('url')
            current_row=int(current_row_node.getAttribute('index'))
            master_dark_checked=int(master_dark_node.getAttribute('checked'))
            master_flat_checked=int(master_flat_node.getAttribute('checked'))
            master_dark_mul_factor=float(master_dark_node.getAttribute('mul'))
            master_flat_mul_factor=float(master_flat_node.getAttribute('mul'))

            try:
                master_bias_url=master_bias_node.getElementsByTagName('url')[0].childNodes[0].data
            except:
                master_bias_url = ''

            try:
                master_dark_url=master_dark_node.getElementsByTagName('url')[0].childNodes[0].data
            except:
                master_dark_url = ''

            try:
                master_flat_url=master_flat_node.getElementsByTagName('url')[0].childNodes[0].data
            except:
                master_flat_url = ''
                        
            biasframelist=[]
            biasListWidgetElements = []    
            if _bias_section:
                self.trace('reading bias-frames section')
                for node in bias_frames_node.getElementsByTagName('image'):
                    if self.progressWasCanceled():
                        return False
                    self.progress.setValue(count)
                    count+=1
                    im_bias_name = node.getAttribute('name')
                    url_bias_node = node.getElementsByTagName('url')[0]
                    im_bias_url = url_bias_node.childNodes[0].data
                    if url_bias_node.attributes.has_key('page'):
                        im_bias_page = url_bias_node.getAttribute('page')
                        biasfrm=utils.Frame(im_bias_url,int(im_bias_page),skip_loading=False, **self.frame_open_args)
                    else:
                        biasfrm=utils.Frame(im_bias_url,0,skip_loading=False, **self.frame_open_args)
                    biasfrm.tool_name=im_bias_name
                    biasfrm.width=imw
                    biasfrm.height=imh
                    biasfrm.mode=dep
                    biasframelist.append(biasfrm)
                    q=Qt.QListWidgetItem(biasfrm.tool_name,None)
                    q.setToolTip(biasfrm.long_tool_name)
                    biasListWidgetElements.append(q)
            
            self.trace('reading dark-frames section')
            
            darkframelist=[]
            darkListWidgetElements = []    
            for node in dark_frames_node.getElementsByTagName('image'):
                if self.progressWasCanceled():
                    return False
                self.progress.setValue(count)
                count+=1
                im_dark_name = node.getAttribute('name')
                url_dark_node = node.getElementsByTagName('url')[0]
                im_dark_url = url_dark_node.childNodes[0].data
                if url_dark_node.attributes.has_key('page'):
                    im_dark_page = url_dark_node.getAttribute('page')
                    darkfrm=utils.Frame(im_dark_url,int(im_dark_page),skip_loading=False, **self.frame_open_args)
                else:
                    darkfrm=utils.Frame(im_dark_url,0,skip_loading=False, **self.frame_open_args)
                darkfrm.tool_name=im_dark_name
                darkfrm.width=imw
                darkfrm.height=imh
                darkfrm.mode=dep
                darkframelist.append(darkfrm)
                q=Qt.QListWidgetItem(darkfrm.tool_name,None)
                q.setToolTip(darkfrm.long_tool_name)
                darkListWidgetElements.append(q)
            
            self.trace('reading flatfield-frames section')
            
            flatframelist=[]
            flatListWidgetElements = []    
            for node in flat_frames_node.getElementsByTagName('image'):
                if self.progressWasCanceled():
                    return False
                self.progress.setValue(count)
                count+=1
                im_flat_name = node.getAttribute('name')
                url_flat_node = node.getElementsByTagName('url')[0]
                im_flat_url = url_flat_node.childNodes[0].data
                if url_flat_node.attributes.has_key('page'):
                    im_flat_page = url_flat_node.getAttribute('page')
                    flatfrm=utils.Frame(im_flat_url,int(im_flat_page),skip_loading=False, **self.frame_open_args)
                else:
                    flatfrm=utils.Frame(im_flat_url,0,skip_loading=False, **self.frame_open_args)
                flatfrm.tool_name=im_flat_name
                flatfrm.width=imw
                flatfrm.height=imh
                flatfrm.mode=dep
                flatframelist.append(flatfrm)
                q=Qt.QListWidgetItem(flatfrm.tool_name,None)
                q.setToolTip(flatfrm.long_tool_name)
                flatListWidgetElements.append(q)
                
            self.trace('reading light-frames section')
            
            framelist=[]  
            listWidgetElements=[]
            for node in pict_frames_node.getElementsByTagName('image'):
                if self.progressWasCanceled():
                        return False
                self.progress.setValue(count)
                count+=1
                im_name = node.getAttribute('name')
                try:
                    im_used = int(node.getAttribute('used'))
                except Exception as exc:
                    st_im_used=str(node.getAttribute('used')).lower()
                    if st_im_used=='false':
                        im_used=0
                    elif st_im_used=='true':
                        im_used=2
                    else:
                        raise exc
                    
                im_url_node  = node.getElementsByTagName('url')[0]
                im_url  = im_url_node.childNodes[0].data

                if im_url_node.attributes.has_key('page'):
                    im_page=im_url_node.getAttribute('page')
                    frm = utils.Frame(im_url,int(im_page),skip_loading=False, **self.frame_open_args)
                else:
                    frm = utils.Frame(im_url,0,skip_loading=False, **self.frame_open_args)


                for point in node.getElementsByTagName('align-point'):
                    point_id = point.getAttribute('id')
                    point_x  = int(point.getAttribute('x'))
                    point_y  = int(point.getAttribute('y'))
                    point_al = bool(point.getAttribute('aligned')=='True')
                    frm.alignpoints.append([point_x, point_y, point_id, point_al])
                
                offset_node=node.getElementsByTagName('offset')[0]
                offset_x=float(offset_node.getAttribute('x'))
                offset_y=float(offset_node.getAttribute('y'))

                if offset_node.attributes.has_key('theta'):
                    offset_t=float(offset_node.getAttribute('theta'))
                else:
                    offset_t=0
                
                frm.tool_name=im_name
                frm.width=imw
                frm.height=imh
                frm.mode=dep
                frm.setOffset([offset_x,offset_y])
                frm.setAngle(offset_t)
                q=Qt.QListWidgetItem(frm.tool_name,None)
                q.setToolTip(frm.long_tool_name)
                q.setCheckState(im_used)
                q.exif_properties=frm.properties
                listWidgetElements.append(q)
                frm.addProperty('listItem',q)
                framelist.append(frm)
            
            starslist=[]
            starsListWidgetElements=[]
            if _fotometric_section:
                self.trace('reading stars section')
                use_image_time=bool(int(photometry_node.getAttribute('time_type')))
                #photometry section
                for star_node in photometry_node.getElementsByTagName('star'):
                    if self.progressWasCanceled():
                        return False
                    s0=int(star_node.getAttribute('x'))
                    s1=int(star_node.getAttribute('y'))
                    s2=str(star_node.getAttribute('name'))
                    s3=float(star_node.getAttribute('inner_radius'))
                    s4=float(star_node.getAttribute('middle_radius'))
                    s5=float(star_node.getAttribute('outer_radius'))
                    s6=bool(int(star_node.getAttribute('reference')))
                    s7=float(star_node.getAttribute('magnitude'))
                    oid=int(star_node.getAttribute('idx'))
                    s=[s0,s1,s2,s3,s4,s5,s6,s7]
                    
                    q=Qt.QListWidgetItem(s2,None)
                    q.setCheckState(int(2*s6))
                    q.original_id=oid
                    starsListWidgetElements.append(q)
                    starslist.append(s)
            else:
                use_image_time=self.use_image_time
                
        except Exception as exc:
            self.current_project_fname=old_fname
            self.unlock()
            self.trace('An error has occurred while reading the project:\n\"'+str(exc)+'\"')
            return self.corruptedMsgBox(str(exc))
       
        self.newProject()
        
        self.current_project_fname=project_fname
                
        self.trace('setting up project environment')
        
        for item in starsListWidgetElements:
            self.wnd.starsListWidget.addItem(item)
        
        for item in biasListWidgetElements:
            self.wnd.biasListWidget.addItem(item)
        
        for item in flatListWidgetElements:
            self.wnd.flatListWidget.addItem(item)
            
        for item in darkListWidgetElements:
            self.wnd.darkListWidget.addItem(item)
            
        for item in listWidgetElements:
            self.wnd.listWidget.addItem(item)
        
        if 'RGB' in dep:
            self.wnd.colorBar._is_rgb=True
            self.wnd.colorBar.current_val=(0.0,0.0,0.0)
        else:
            self.wnd.colorBar._is_rgb=False
            self.wnd.colorBar.current_val=0.0     
        
        self.currentWidth=imw
        self.currentHeight=imh
        self.currentDepht=dep
        self.updateBayerComponents()
        self.framelist=framelist
        self.biasframelist=biasframelist
        self.darkframelist=darkframelist
        self.flatframelist=flatframelist
        self.starslist=starslist
        self.image_idx=current_row
        self.master_bias_file=master_bias_url
        self.master_dark_file=master_dark_url
        self.master_flat_file=master_flat_url
        self.wnd.listWidget.setCurrentRow(current_row)
        self.autoalign_rectangle=(ar_w, ar_h)
        self.max_points=max_points
        self.min_quality=min_quality
        self.auto_align_use_whole_image=use_whole_image
        self.wnd.imageDateCheckBox.setCheckState(2*use_image_time)
        self.current_dir=current_dir
        
        if (len(self.framelist)>0):
            self._unlock_cap_ctrls()
            
            if bayer_mode >= 0:
                self.wnd.rawGroupBox.setChecked(True)
                self.wnd.bayerComboBox.setCurrentIndex(bayer_mode)
            else:
                self.wnd.rawGroupBox.setChecked(False)
            
        if _bias_section:
            self.wnd.masterBiasCheckBox.setCheckState(master_bias_checked)
            self.wnd.masterBiasLineEdit.setText(master_bias_url)
            self.wnd.biasMulDoubleSpinBox.setValue(master_bias_mul_factor)
            if (len(self.biasframelist)>0):
                self.wnd.biasClearPushButton.setEnabled(True)

        self.wnd.masterDarkCheckBox.setCheckState(master_dark_checked)
        self.wnd.masterDarkLineEdit.setText(master_dark_url)
        self.wnd.darkMulDoubleSpinBox.setValue(master_dark_mul_factor)
        if (len(self.darkframelist)>0):
            self.wnd.darkClearPushButton.setEnabled(True)

        self.wnd.masterFlatCheckBox.setCheckState(master_flat_checked)
        self.wnd.masterFlatLineEdit.setText(master_flat_url)
        self.wnd.flatMulDoubleSpinBox.setValue(master_flat_mul_factor)
        if (len(self.flatframelist)>0):
            self.wnd.flatClearPushButton.setEnabled(True)
        self.trace('project fully loaded\n')
        self.wnd.setWindowTitle(str(paths.PROGRAM_NAME)+' ['+self.current_project_fname+']')    
        self.unlock()
        
    def autoDetectAlignPoints(self):
        i = self.framelist[self.image_idx].getData(asarray=True)
        i = i.astype(np.float32)
        
        if 'RGB' in self.currentDepht:
            i=i.sum(2)/3.0
        
        rw=self.autoalign_rectangle[0]
        rh=self.autoalign_rectangle[1]
        
        hh=2*rh
        ww=2*rw
        
        g=i[hh:-hh,ww:-ww]

        del i
        
        min_dist = int(math.ceil((rw**2+rh**2)**0.5))

        if self.checked_autodetect_min_quality==2:
            self.min_quality=1
            points = []
            max_iteration=25
            while (len(points) < ((self.max_points/2)+1)) and (max_iteration>0):
                points = cv2.goodFeaturesToTrack(g,self.max_points,self.min_quality,min_dist)
                if points is None:
                    points=[]
                self.min_quality*=0.75
                max_iteration-=1

        else:
            points = cv2.goodFeaturesToTrack(g,self.max_points,self.min_quality,min_dist)
            if points is None:
                points=[]
            
        if len(points) > 0:            
            for p in points:
                self.point_idx=self.addAlignPoint()
                self.wnd.spinBoxXAlign.setValue(p[0][0]+ww)
                self.wnd.spinBoxYAlign.setValue(p[0][1]+hh)
                
        elif self.checked_autodetect_min_quality:
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr("No suitable points foud!"))
            msgBox.setInformativeText(tr("Try to add them manually."))
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()
        else:
            msgBox = Qt.QMessageBox()
            msgBox.setText(tr("No suitable points foud!"))
            msgBox.setInformativeText(tr("Try to modify the alignment settings."))
            msgBox.setIcon(Qt.QMessageBox.Warning)
            msgBox.exec_()

    def autoSetAlignPoint(self):
        image_idx=self.wnd.listWidget.currentRow()
        current_point=self.wnd.alignPointsListWidget.currentRow()
        self.statusBar.showMessage(tr('detecting points, please wait...'))
        
        current_frame = self.framelist[image_idx]
        
        for point_idx in range(len(current_frame.alignpoints)):
            self.point_idx=point_idx
            if not self._autoPointCv(point_idx, image_idx):
                self.wnd.alignPointsListWidget.setCurrentRow(current_point)
                return False
        self.wnd.alignPointsListWidget.setCurrentRow(current_point)
        self.point_idx=current_point

    def _autoPointCv(self, point_idx, image_idx=0):
        point = self.framelist[image_idx].alignpoints[point_idx]


        #if already detected and not moved
        skip=True   
        for i in range(len(self.framelist)):
            skip &= self.framelist[i].alignpoints[point_idx][3]

        #then skip            
        if skip:
            return True

        r_w=Int(self.autoalign_rectangle[0]/2)
        r_h=Int(self.autoalign_rectangle[1]/2)
        x1=point[0]-r_w
        x2=point[0]+r_w
        y1=point[1]-r_h
        y2=point[1]+r_h
        
        rawi = self.framelist[image_idx].getData(asarray=True)
        refi = rawi[y1:y2,x1:x2]
        del rawi
        
        cv_ref = refi.astype(np.float32)
        del refi
        
        self.progress.setMaximum(len(self.framelist)-1)
        self.lock()
        
        for i in range(len(self.framelist)):
            self.progress.setValue(i)

            frm = self.framelist[i]

            if self.progressWasCanceled():
                return False

            frm.alignpoints[point_idx][3]=True                

            if i == image_idx:
                continue
            self.statusBar.showMessage(tr('detecting point ')+str(point_idx+1)+tr(' of ')+str(len(self.framelist[image_idx].alignpoints))+tr(' on image ')+str(i)+tr(' of ')+str(len(self.framelist)-1))
            
            if self.auto_align_use_whole_image==2:
                rawi=frm.getData(asarray=True)
            else:
                rawi=frm.getData(asarray=True)[y1-r_h:y2+r_h,x1-r_w:x2+r_w]

            cv_im=rawi.astype(np.float32)
            
            del rawi
            
            min_dif = None
            min_point=(0,0)
            #TODO: fix error occurring when align-rectangle is outside the image
            res = cv2.matchTemplate(cv_im,cv_ref,self.current_match_mode)
            minmax = cv2.minMaxLoc(res)
            del res            
            if self.auto_align_use_whole_image==2:
                frm.alignpoints[point_idx][0]=minmax[2][0]+r_w
                frm.alignpoints[point_idx][1]=minmax[2][1]+r_h
            else:
                frm.alignpoints[point_idx][0]=minmax[2][0]+x1
                frm.alignpoints[point_idx][1]=minmax[2][1]+y1
            
        self.unlock()
        
        return True
    
    def doAlign(self, *arg, **args):
        return self.align()
        
    def align(self,do_reset=None,do_align=None,do_derot=None):
        
        result=None
        
        if not(do_reset is None) or not(do_align is None) or not(do_derot is None):
            align=(do_align==True)
            derotate=(do_derot==True)
            reset=(do_reset==True)
        elif self.align_dlg.exec_():
            align_derot = self.align_dlg.alignDerotateRadioButton.isChecked()
            align = align_derot or self.align_dlg.alignOnlyRadioButton.isChecked()
            derotate = align_derot or self.align_dlg.derotateOnlyRadioButton.isChecked()
            reset = self.align_dlg.resetRadioButton.isChecked()
        else:
            return False
        
        if reset:
            self.trace('Resetting alignment...')
            self.progress.setMaximum(len(self.framelist))
            self.lock()
            count=0
            for i in self.framelist:
                count+=1
                self.progress.setValue(count)
                if i.isUsed():
                    self.trace(' Image ' + i.name +' -> shift = (0.0, 0.0)  angle=0.0')
                    self.statusBar.showMessage(tr('Resetting alignment for image')+' '+i.name)
                    i.angle=0
                    i.offset=(0,0)
                else:
                    self.trace(' Skipping image ' + i.name)
            self.unlock()
        else:
            self.is_aligning = True
            if self.current_align_method == 0:
                result = self._alignPhaseCorrelation(align, derotate)
            elif self.current_align_method == 1:
                result = self._alignAlignPoints(align, derotate)
            self.is_aligning = False
            
        return result
    
    def _derotateAlignPoints(self, var_matrix):
        
        vecslist=[]   
        
        for i in self.framelist:
            _tmp = []
            
            for p in i.alignpoints:                
                _tmp.append(np.array(p[0:2])-i.offset[0:2])
                
            vecslist.append(_tmp)
            
        del _tmp
                    
        refs=vecslist[0]
                       
        nvecs = len(vecslist[0])
        
        angles=[0]

        for vecs in vecslist[1:]: 
            angle=0
            for i in range(nvecs):                

                x1=refs[i][0]
                y1=refs[i][1]
                x2=vecs[i][0]
                y2=vecs[i][1]
                
                vmod = (vecs[i][0]**2 + vecs[i][1]**2)**0.5
                rmod = (refs[i][0]**2 + refs[i][1]**2)**0.5
                
                if (vmod==0) or (rmod==0):
                    w[i]=0
                
                cosa=((x1*x2+y1*y2)/(vmod*rmod))
                sina=((x2*y1-x1*y2)/(vmod*rmod))
                
                if cosa>1:
                    #this should never never never occurs
                    cosa=1.0
                    
                if sina>1:
                    #this should never never never occurs
                    sina=1.0
                    
                angle+=(math.atan2(sina,cosa)*180.0/math.pi)*var_matrix[i]
        
            angle/=var_matrix.sum()

            angles.append(angle)

        for i in range(len(self.framelist)):
            self.framelist[i].angle=-angles[i]
        
    def _alignAlignPoints(self, align, derotate):
        
        if len(self.framelist) == 0:
            return False

        total_points = len(self.framelist[0].alignpoints)
        total_images = len(self.framelist)
        
        if (len(self.framelist) > 0) and (total_points>0):
            self.statusBar.showMessage(tr('Calculating image shift, please wait...'))

            self.progress.setMaximum(total_images-1)
            self.lock()
            
            mat = np.zeros((total_images,total_points,2))
            
            for i in range(total_images):
                for j in range(total_points):
                    p = self.framelist[i].alignpoints[j]
                    mat[i,j,0]=p[0]
                    mat[i,j,1]=p[1]
            
            x_stk = mat[...,0].mean()
            y_stk = mat[...,1].mean()
            
            mat2 = mat-[x_stk,y_stk]
            
            var = np.empty((len(mat[0])))
            avg = np.empty((len(mat[0]),2))

            for i in range(len(mat[0])):
                dist=(mat2[...,i,0]**2+mat2[...,i,1]**2)
                var[i]=dist.var()
                 
            del mat2

            w = 1/(var+0.00000001) #Added 0.00000001 to avoid division by zero
            del var
            
            if align:
                for img in self.framelist:
                    x=0
                    y=0
                    for j in range(len(img.alignpoints)):
                        x+=img.alignpoints[j][0]*w[j]
                        y+=img.alignpoints[j][1]*w[j]
                    
                    img.offset[0]=(x/w.sum())
                    img.offset[1]=(y/w.sum())

                    self.progress.setValue(i)
                    if ((i%25)==0) and self.progressWasCanceled():
                        return False
            else:
                for img in self.framelist:
                    img.offset[0]=0
                    img.offset[1]=0
                    
            self.unlock()
            self.statusBar.showMessage(tr('DONE'))
            
            if (total_points > 1) and derotate:
                self._derotateAlignPoints(w)
            
                rotation_center = (self.currentWidth/2,self.currentHeight/2)
            
                #compesate shift for rotation
                for img in self.framelist:
                    x=img.offset[0]-rotation_center[0]
                    y=img.offset[1]-rotation_center[1]
                    alpha = math.pi*img.angle/180.0

                    cosa  = math.cos(alpha)
                    sina  = math.sin(alpha)

                    #new shift
                    img.offset[0]=self.currentWidth/2+(x*cosa+y*sina)
                    img.offset[1]=self.currentWidth/2+(y*cosa-x*sina)
            else:
                for img in self.framelist:
                    img.angle=0
                    
            self.progress.setMaximum(3*len(self.framelist))
            
            if align:
                self.lock()
                self.statusBar.showMessage(tr('Calculating references, please wait...'))
                
                count=0
            
                ref_set=False
            
                for img in self.framelist:
                    self.progress.setValue(count)
                    count+=1
                    if self.progressWasCanceled():
                        return False
    
                    if img.isUsed():
                    
                        if not ref_set:
                            ref_x=img.offset[0]
                            ref_y=img.offset[1]
                            ref_set=True
                        else:
                            ref_x = min(ref_x,img.offset[0])
                            ref_y = min(ref_y,img.offset[1])
    
    
                for img in self.framelist:
                    self.progress.setValue(count)
                    count+=1

                    if self.progressWasCanceled():
                        return False
                    
                    if img.isUsed():
                        img.offset[0]=float(img.offset[0]-ref_x)
                        img.offset[1]=float(img.offset[1]-ref_y)
    
                self.progress.reset()
        
                self.unlock()
            else:
                for img in self.framelist:
                    img.setOffset([0,0])

                
    def _alignPhaseCorrelation(self, align, derotate):
        
        
        old_state = self.wnd.zoomCheckBox.checkState()
        self.wnd.zoomCheckBox.setCheckState(1)
        self.wnd.zoomCheckBox.setEnabled(False)
        
        self.statusBar.showMessage(tr('Computing phase correlation, please wait...'))
        self.clearImage()
        ref_set=False
        self.lock()
        self.progress.setMaximum(len(self.framelist))
        self.wnd.MainFrame.setEnabled(True)
        ref = None
            
        mask = utils.generateCosBell(self.currentWidth,self.currentHeight)
        old_rgb_mode = self.wnd.colorBar._is_rgb
        self.wnd.colorBar._is_rgb=False
        
        count=0
        
        sharp1=self.wnd.sharp1DoubleSpinBox.value()
        sharp2=self.wnd.sharp2DoubleSpinBox.value()
        
        for img in self.framelist:
            
            self.progress.setValue(count)
            count+=1

            if self.progressWasCanceled():
                self.wnd.colorBar._is_rgb=old_rgb_mode
                self.clearImage()
                self.unlock()
                self.wnd.zoomCheckBox.setEnabled(True)
                self.wnd.zoomCheckBox.setCheckState(old_state)
                self.statusBar.showMessage(tr('canceled by the user'))
                return False
            
            if img.isUsed():
                self.qapp.processEvents()
                if ref is None:
                    ref = img
                    self.trace('\n using image '+img.name+' as reference')
                    ref_data = ref.getData(asarray=True)
                    if len(ref_data.shape)==3:
                        ref_data=ref_data.sum(2)
                    ref_data*=mask
                    ref.setOffset([0,0])
                else:
                    self.trace('\n registering image '+img.name)
                    img_data=img.getData(asarray=True)
                    if len(img_data.shape)==3:
                        img_data=img_data.sum(2)
                    img_data*=mask
                    data=utils.register_image(ref_data,img_data,sharp1,sharp2,align,derotate,self.phase_interpolation_order)
                    self._phase_align_data=(data[1],data[2],data[0].shape)
                    self.statusBar.showMessage(tr('shift: ')+str(data[1])+', '+
                                               tr('rotation: ')+str(data[2]))
                    del img_data
                    if not(data[0] is None) and (self.checked_show_phase_img==2):
                        self.showImage(utils.arrayToQImage(data[0]))
                    img.setOffset(data[1])
                    img.setAngle(data[2])
                    
        del mask
        self._phase_align_data=None
        self.wnd.colorBar._is_rgb=old_rgb_mode
        self.clearImage()
        self.wnd.zoomCheckBox.setEnabled(True)
        self.wnd.zoomCheckBox.setCheckState(old_state)
        self.unlock()
        self.statusBar.showMessage(tr('DONE'))       
    

    def getStackingMethod(self, method, framelist, bias_image, dark_image, flat_image, **args):
        """
        available stacking methods:
         _______________________
        |   method   |   name   |
        |____________|__________|
        |     0      |  average |
        |____________|__________|
        |     1      |  median  |
        |____________|__________|
        |     2      |  k-sigma |
        |____________|__________|
        |     3      | std.dev. |
        |____________|__________|
        |     4      | variance |
        |____________|__________|
        |     5      |  maximum |
        |____________|__________|
        |     6      |  minimum |
        |____________|__________|
        |     7      |  product |
        |____________|__________|
        
        """
        if method==0:
            return self.average(framelist, bias_image, dark_image, flat_image, **args)
        elif method==1:
            return self.median(framelist, bias_image, dark_image, flat_image, **args)
        elif method==2:
            return self.sigmaclip(framelist, bias_image, dark_image, flat_image, **args)
        elif method==3:
            return self.stddev(framelist, bias_image, dark_image, flat_image, **args)
        elif method==4:
            return self.variance(framelist, bias_image, dark_image, flat_image, **args)
        elif method==5:
            return self.maximum(framelist, bias_image, dark_image, flat_image, **args)
        elif method==6:
            return self.minimum(framelist, bias_image, dark_image, flat_image, **args)
        elif method==7:
            return self.product(framelist, bias_image, dark_image, flat_image, **args)
        else:
            #this should never happen
            self.trace("Something that sould never happen has just happened!")
            self.trace("An unknonw stacking method has been selected")
            return None
    
    def doStack(self,*arg,**args):
        self.stack()
    
    def stack(self,method=None):
        
        self.clearResult()
        """
        selecting method and setting options
        before stacking
        """
        
        if(self.wnd.masterBiasCheckBox.checkState() == 2):
            self.stack_dlg.tabWidget.setTabEnabled(1,False)
        else:
            self.stack_dlg.tabWidget.setTabEnabled(1,True)
            
        if(self.wnd.masterDarkCheckBox.checkState() == 2):
            self.stack_dlg.tabWidget.setTabEnabled(2,False)
        else:
            self.stack_dlg.tabWidget.setTabEnabled(2,True)
        
        if(self.wnd.masterFlatCheckBox.checkState() == 2):
            self.stack_dlg.tabWidget.setTabEnabled(3,False)
        else:
            self.stack_dlg.tabWidget.setTabEnabled(3,True)
        
        if not(method is None):
            bias_method=method
            dark_method=method
            flat_method=method
            lght_method=method
            
            bias_args={'lk':self.stack_dlg.biasLKappa.value(),
                        'hk':self.stack_dlg.biasHKappa.value(),
                        'iterations':self.stack_dlg.biasKIters.value(),
                        'debayerize_result':False}
            
            dark_args={'lk':self.stack_dlg.darkLKappa.value(),
                       'hk':self.stack_dlg.darkHKappa.value(),
                       'iterations':self.stack_dlg.darkKIters.value(),
                       'debayerize_result':False}
            
            flat_args={'lk':self.stack_dlg.flatLKappa.value(),
                       'hk':self.stack_dlg.flatHKappa.value(),
                       'iterations':self.stack_dlg.flatKIters.value(),
                       'debayerize_result':False}
                       
            lght_args={'lk':self.stack_dlg.ligthLKappa.value(),
                       'hk':self.stack_dlg.ligthHKappa.value(),
                       'iterations':self.stack_dlg.ligthKIters.value(),
                       'debayerize_result':True}
            
        elif self.stack_dlg.exec_():
            bias_method=self.stack_dlg.biasStackingMethodComboBox.currentIndex()
            dark_method=self.stack_dlg.darkStackingMethodComboBox.currentIndex()
            flat_method=self.stack_dlg.flatStackingMethodComboBox.currentIndex()
            lght_method=self.stack_dlg.ligthStackingMethodComboBox.currentIndex()
            
            bias_args={'lk':self.stack_dlg.biasLKappa.value(),
                        'hk':self.stack_dlg.biasHKappa.value(),
                        'iterations':self.stack_dlg.biasKIters.value(),
                        'debayerize_result':False}
            
            dark_args={'lk':self.stack_dlg.darkLKappa.value(),
                       'hk':self.stack_dlg.darkHKappa.value(),
                       'iterations':self.stack_dlg.darkKIters.value(),
                       'debayerize_result':False}
            
            flat_args={'lk':self.stack_dlg.flatLKappa.value(),
                       'hk':self.stack_dlg.flatHKappa.value(),
                       'iterations':self.stack_dlg.flatKIters.value(),
                       'debayerize_result':False}
                       
            lght_args={'lk':self.stack_dlg.ligthLKappa.value(),
                       'hk':self.stack_dlg.ligthHKappa.value(),
                       'iterations':self.stack_dlg.ligthKIters.value(),
                       'debayerize_result':True}
        else:
            return False
        
        self.lock()
        
        self.master_bias_file = str(self.wnd.masterBiasLineEdit.text())
        self.master_dark_file = str(self.wnd.masterDarkLineEdit.text())
        self.master_flat_file = str(self.wnd.masterFlatLineEdit.text())
        
        if (self.wnd.masterBiasCheckBox.checkState() == 2):
            if os.path.isfile(self.master_bias_file):
                bas=utils.Frame(self.master_bias_file, **self.frame_open_args)
                self._bas=bas.getData(asarray=True, ftype=self.ftype)
            elif self.master_bias_file.replace(' ','').replace('\t','') == '':
                pass #ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("Cannot open \'"+self.master_bias_file+"\':"))
                msgBox.setInformativeText(tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif (len(self.biasframelist)>0):
            self.statusBar.showMessage(tr('Creating master-dark, please wait...'))
            _bas=self.getStackingMethod(bias_method,self.biasframelist, None, None, None, **bias_args)
            if _bas is None:
                return False
            else:
                self._bas=_bas
        
        if (self.wnd.masterDarkCheckBox.checkState() == 2):
            if os.path.isfile(self.master_dark_file):
                drk=utils.Frame(self.master_dark_file, **self.frame_open_args)
                self._drk=drk.getData(asarray=True, ftype=self.ftype)
            elif self.master_dark_file.replace(' ','').replace('\t','') == '':
                pass #ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("Cannot open \'"+self.master_dark_file+"\':"))
                msgBox.setInformativeText(tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif (len(self.darkframelist)>0):
            self.statusBar.showMessage(tr('Creating master-dark, please wait...'))
            _drk=self.getStackingMethod(dark_method,self.darkframelist, None, None, None, **dark_args)
            if _drk is None:
                return False
            else:
                self._drk=_drk
                
        if (self.wnd.masterFlatCheckBox.checkState() == 2):
            if os.path.isfile(self.master_flat_file):
                flt=utils.Frame(self.master_flat_file, **self.frame_open_args)
                self._flt=flt.getData(asarray=True, ftype=self.ftype)
            elif self.master_flat_file.replace(' ','').replace('\t','') == '':
                pass #ignore
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("Cannot open \'"+self.master_dark_file+"\':"))
                msgBox.setInformativeText(tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif (len(self.flatframelist)>0):
            self.statusBar.showMessage(tr('Creating master-flat, please wait...'))
            _flt=self.getStackingMethod(flat_method,self.flatframelist, None, None, None,**flat_args)
            if _flt is None:
                return False
            else:
                self._flt=_flt
        
        self.statusBar.showMessage(tr('Stacking images, please wait...'))
        
        _stk=self.getStackingMethod(lght_method,self.framelist, self._bas, self._drk, self._flt,**lght_args)
        
        if(_stk is None):
            self.unlock()
            return False
        else:
            self._stk=_stk-_stk.min()
            self.statusBar.showMessage(tr('Generating histograhms...'))
            self._hst=utils.generateHistograhms(self._stk,256) #TODO:make a user's control?
            self.qapp.processEvents()
            self.statusBar.showMessage(tr('Generating preview...'))
            self.qapp.processEvents()
            self._preview_data=utils.generatePreview(self._stk,512)
            self._preview_image=utils.arrayToQImage(self._preview_data,bw_jet=self.use_colormap_jet)
            del _stk
            self.updateResultImage()
            self.activateResultControls()
            self.statusBar.showMessage(tr('DONE'))
        self.unlock()
        
    def generateMasters(self, bias_image=None, dark_image=None, flat_image=None):
        self.trace("generating master frames")
        
        if not (bias_image is None):
            
            master_bias=(bias_image*self.master_bias_mul_factor)
            
        else:
            master_bias=None
            
        if not (dark_image is None):
            
            if not (master_bias is None):
                master_dark=(dark_image-master_bias)*self.master_dark_mul_factor
            else:
                master_dark=dark_image*self.master_dark_mul_factor
            
            mean_dark=master_dark.mean()
            ddev_dark=master_dark.var()
            dmax=master_dark.max()
            dmin=master_dark.min()
            delta=dmax-dmin
            hot_pixels=[]
            
            if ddev_dark>0:
                fac=(ddev_dark)/(1-(mean_dark-dmin)/delta)
                
                max_number=int(0.005*np.array(master_dark.shape[0:2]).prod())
                
                mm=master_dark.max(0)
                
                n=3
                hot_pixels=np.argwhere((master_dark-dmin)>n*fac)
                
                while len(hot_pixels) > max_number:
                    n+=1
                    hot_pixels=np.argwhere((master_dark-dmin)>n*fac)            
            
            self.trace("Found "+str(len(hot_pixels))+" hot pixels")
            
        else:
            master_dark=None
            hot_pixels=None
            
        if not (flat_image is None):
            
            # this should avoid division by zero
            zero_mask = ((flat_image == 0).astype(self.ftype))*flat_image.max()
            corrected = flat_image+zero_mask
            del zero_mask
            normalizer = corrected.min()
            master_flat=((corrected/normalizer)*self.master_flat_mul_factor)
            del corrected
            
        else:
            master_flat=None
            
        return (master_bias, master_dark, master_flat, hot_pixels)
    
    def calibrate(self, image, master_bias=None, master_dark=None, master_flat=None, hot_pixels=None, debayerize_result=False, **args):
                
        if (master_bias is None) and (master_dark is None) and (master_flat is None):
            self.trace("skipping image calibration")
        else:
            self.trace("calibrating image...")
            if not(master_bias is None):
                self.trace("calibrating image: subtracting bias")
                image -=  master_bias
                                    
            if not(master_dark is None):
                self.trace("calibrating image: subtracting master dark")
                image -=  master_dark
            
            if not(hot_pixels is None):
                self.trace("calibrating image: correcting for hot pixels")
                
            
                """
                
                The HOT pixels will be replaced by the mean value of its neighbours X
                
                                         NORMAL IMAGE
                                    +---+---+---+---+---+
                                    |RGB|RGB|RGB|RGB|RGB|
                                    +---+---+---+---+---+
                                    |RGB|RGB| X |RGB|RGB|
                                    +---+---+---+---+---+
                                    |RGB| X |HOT| X |RGB|
                                    +---+---+---+---+---+
                                    |RGB|RGB| X |RGB|RGB|
                                    +---+---+---+---+---+
                                    |RGB|RGB|RGB|RGB|RGB|
                                    +---+---+---+---+---+

                                          RAW IAMGE
                                    +---+---+---+---+---+
                                    | R | G | X | G | R |
                                    +---+---+---+---+---+
                                    | G | B | G | B | G |
                                    +---+---+---+---+---+
                                    | X | G |HOT| G | X |
                                    +---+---+---+---+---+
                                    | G | B | G | B | G |
                                    +---+---+---+---+---+
                                    | R | G | X | G | R |
                                    +---+---+---+---+---+
                                    
                This is better than simply assign to it a ZERO value.
                
                """
                
                #self.traceTimeStart("Removing "+str(len(hot_pixels))+" hot pixels...")
                for hotp in hot_pixels:
                    hotp_x=hotp[1]
                    hotp_y=hotp[0]
                    image[hotp_y,hotp_x]=utils.getNeighboursAverage(image,hotp_x,hotp_y,self.wnd.rawGroupBox.isChecked()==2)
                #self.traceTimeStop()    
                
            if not(master_flat is None):
                self.trace("calibrating image: dividing by master flat")
                image /= master_flat  
                
        
        
        if debayerize_result:
            debay = self.debayerize(image)
            return debay
        else:
            return image
            
    def registerImages(self, img, img_data):
        if img.angle!=0:
            
            img_data = sp.ndimage.interpolation.rotate(img_data,img.angle,order=self.interpolation_order,reshape=False,mode='constant',cval=0.0)
            
        else:
            self.trace("skipping rotation")
        
        shift=np.zeros([len(img_data.shape)])
        shift[0]=-img.offset[1]
        shift[1]=-img.offset[0]
        
        if (shift[0]!=0) or (shift[1]!=0):
            
            self.trace("shifting of "+str(shift[0:2]))
            img_data = sp.ndimage.interpolation.shift(img_data,shift,order=self.interpolation_order,mode='constant',cval=0.0)
            
        else:
            self.trace("skipping shift")
        del shift

        return img_data
    
    def nativeOperationOnImages(self, operation, name, framelist ,bias_image=None, dark_image=None,
                                flat_image=None, post_operation = None, **args):
        
        result = None
        
        master_bias, master_dark, master_flat, hot_pixels = self.generateMasters(bias_image,dark_image,flat_image)
        
        total = len(framelist)
        
        self.trace('Computing ' + str(name) + ', please wait...')
        
        self.progress.reset()
        self.progress.setMaximum(4*(total-1))
        
        count = 0
        progress_count=0
        
        if 'chunks_size' in args and args['chunks_size']>1:
            chunks=[]
            chunks_size=int(args['chunks_size'])
        else:
            chunks_size=1
        
        for img in framelist:
   
            self.progress.setValue(progress_count)
            progress_count+=1
            
            if self.progressWasCanceled():
                return None
            
            if img.isUsed():
                count+=1
                self.trace('\nUsing image '+img.name)
            else:
                progress_count+=3
                self.trace('\nSkipping image '+img.name)
                continue
            
            
            r=img.getData(asarray=True, ftype=self.ftype)
            
            if self.progressWasCanceled():
                return None
            
            self.progress.setValue(progress_count)
            progress_count+=1

            if img.isRGB() and (r.shape[2]>3):
                r = r[...,0:3]
                
            r = self.calibrate(r, master_bias, master_dark, master_flat, hot_pixels, **args)
            
            if self.progressWasCanceled():
                return None
            
            self.progress.setValue(progress_count)
            progress_count+=1
            
            r = self.registerImages(img,r)
            
            if self.progressWasCanceled():
                return None
            
            self.progress.setValue(progress_count)
            progress_count+=1
            
            
            if chunks_size>1:
                if len(chunks) <= chunks_size:
                    chunks.append(r)
                else:
                    if 'numpy_like' in args and args['numpy_like']==True:
                        result=operation(chunks, axis=0)
                    else:
                        result=operation(chunks)
                    chunks=[result,]
            else:
                if result is None:
                    result=r.copy()
                else:
                    if 'numpy_like' in args and args['numpy_like']==True:
                        result=operation((result,r), axis=0)
                    else:
                        result=operation(result,r)

            del r
                    
        
        if chunks_size>1 and len(chunks) > 1:
            
            if 'numpy_like' in args and args['numpy_like']==True:
                result=operation(chunks, axis=0)
            else:
                result=operation(chunks)
            
            
        self.progress.setValue(4*(total-1))  
        self.statusBar.showMessage(tr('Computing final image...'))
        
        if not (post_operation is None):
            result=post_operation(result,count)
            
        
        self.statusBar.clearMessage()
        
        return result

    """
    Executes the 'operation' on each subregion of size 'subw'x'subh' of images stored in
    temporary files listed in filelist. the original shape of the images must be passed
    as 'shape'
    """
    #TODO: make option to change subw and subh
    def _operationOnSubregions(self,operation, filelist, shape, title="", subw=256, subh=256, **args):

        n_y_subs=shape[0]/subh
        n_x_subs=shape[1]/subw
        
        total_subs=(n_x_subs+1)*(n_y_subs+1)
        
        self.trace("Executing "+ str(title)+": splitting images in "+str(total_subs)+" sub-regions")
        self.statusBar.showMessage(tr('Computing') +' '+ str(title) + ', ' + tr('please wait...'))
        self.progress.reset
        self.progress.setMaximum(total_subs*(len(filelist)+1))
        progress_count = 0
        
        x=0
        y=0
        
        result=np.zeros(shape)
        
        mmaps = []
        
        if self.checked_compressed_temp==0:
            for fl in filelist:
                progress_count+=1
                self.progress.setValue(progress_count)                                
                if self.progressWasCanceled():
                    return None
                mmaps.append(utils.loadTmpArray(fl))
        
        count=0
        while y <= n_y_subs:
            x=0
            while x <= n_x_subs:
                
                xst=x*subw
                xnd=(x+1)*subw
                yst=y*subh
                ynd=(y+1)*subh
                
                lst=[]

                if self.checked_compressed_temp==2:
                    for fl in filelist:
                        progress_count+=1
                        self.progress.setValue(progress_count)                                
                        if self.progressWasCanceled():
                            return None
                        n=utils.loadTmpArray(fl)
                        sub=n[yst:ynd,xst:xnd].copy()
                        lst.append(sub)
                else:
                    for n in mmaps:
                        progress_count+=1
                        self.progress.setValue(progress_count)                                
                        if self.progressWasCanceled():
                            return None
                        sub=n[yst:ynd,xst:xnd].copy()
                        lst.append(sub)
                count+=1
                msg = tr('Computing ')+str(title)+tr(' on subregion ')+str(count)+tr(' of ')+str(total_subs)
                self.trace(msg)
                self.statusBar.showMessage(msg)
                self.qapp.processEvents()
                
                if len(args)>0:
                    try:
                        operation(lst, axis=0, out=result[yst:ynd,xst:xnd],**args)
                    except:
                        operation(lst, axis=0, out=result[yst:ynd,xst:xnd])
                else:
                    operation(lst, axis=0, out=result[yst:ynd,xst:xnd])
                del lst
                x+=1
            y+=1
        del mmaps
        return result
    
    def sigmaClipping(self,array, axis=-1, out=None, **args):
        
        lkappa = args['lk']
        hkappa = args['hk']
        itr = args['iterations']        

        clipped = np.ma.masked_array(array)
        
        for i in range(itr):
            sigma = np.std(array, axis=axis)
            mean = np.mean(array, axis=axis)

            min_clip=mean-lkappa*sigma
            max_clip=mean+hkappa*sigma
            
            del sigma
            del mean
            
            clipped = np.ma.masked_less(clipped, min_clip)
            clipped = np.ma.masked_greater(clipped, max_clip)
            
            del min_clip
            del max_clip
            
        if out is None:
            return np.ma.average(clipped, axis=axis)
        else:
            out[...] = np.ma.average(clipped, axis=axis)
    
    def medianSigmaClipping(self,array, axis=-1, out=None, **args): #TODO:check -> validate -> add functionality
        
        lkappa = args['lmk']
        hkappa = args['hmk']
        itr = args['miterations']        

        clipped = np.ma.masked_array(array)
        
        for i in range(itr):
            sigma = np.std(array, axis=axis)
            mean = np.median(array, axis=axis)

            min_clip=mean-lkappa*sigma
            max_clip=mean+hkappa*sigma
            
            del sigma
            del mean
            
            clipped = np.ma.masked_less(clipped, min_clip)
            clipped = np.ma.masked_greater(clipped, max_clip)
            
            del min_clip
            del max_clip
            
        if out is None:
            return np.ma.median(clipped, axis=axis)
        else:
            out[...] = np.ma.median(clipped, axis=axis)
            
        
    def average(self,framelist , bias_image=None, dark_image=None, flat_image=None, **args):
        return self.nativeOperationOnImages(np.add,tr('average'),framelist,
                                            bias_image, dark_image, flat_image,
                                            post_operation = np.divide, **args)
    
    def stddev(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        avg=self.average(framelist,  bias_image, dark_image, flat_image)
        return self.nativeOperationOnImages(lambda a1,a2: (a2-avg)**2,tr('standard deviation'),framelist,
                                            dark_image, flat_image, post_operation=lambda x,n: np.sqrt(x/(n-1)), **args)
        
    def variance(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        #return self.operationOnImages(np.var,tr('variance'),framelist, dark_image, flat_image)
        avg=self.average(framelist,  bias_image, dark_image, flat_image)
        return self.nativeOperationOnImages(lambda a1,a2: (a2-avg)**2,tr('variance'),framelist,
                                            dark_image, flat_image, post_operation=lambda x,n: x/(n-1), **args)
        
    #TODO: try to make a native function
    def sigmaclip(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(self.sigmaClipping,tr('sigma clipping'),framelist,  bias_image, dark_image, flat_image, **args)
    
    #TODO: try to make a native function 
    def median(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        return self.operationOnImages(np.median,tr('median'),framelist,  bias_image, dark_image, flat_image, **args)
            
    def maximum(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        #return self.operationOnImages(np.max,tr('maximum'),framelist, dark_image, flat_image)
        return self.nativeOperationOnImages(np.max,tr('maximum'),framelist,  bias_image, dark_image, flat_image,
                                            numpy_like=True, **args)
    
    def minimum(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        #return self.operationOnImages(np.min,tr('minimum'),framelist, dark_image, flat_image)
        return self.nativeOperationOnImages(np.min,tr('minimum'),framelist,  bias_image, dark_image, flat_image,
                                            numpy_like=True, **args)

    def product(self,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
        #return self.operationOnImages(np.prod,tr('product'),framelist, dark_image, flat_image)
        return self.nativeOperationOnImages(np.prod,tr('product'),framelist, bias_image, dark_image, flat_image, numpy_like=True, **args)
    
    

    def operationOnImages(self,operation, name,framelist, bias_image=None, dark_image=None, flat_image=None, **args):
            
        result=None
                
        master_bias, master_dark, master_flat, hot_pixels = self.generateMasters(bias_image,dark_image,flat_image)

        total = len(framelist)
        
        self.statusBar.showMessage(tr('Registering images, please wait...'))
        
        self.progress.reset()
        self.progress.setMaximum(4*(total-1))
        
        count = 0
        progress_count=0
        
        original_shape=None
        
        tmpfilelist=[]
        
        for img in framelist:

            if self.progressWasCanceled():
                return False
                
            self.progress.setValue(progress_count)
            progress_count+=1
            
            if img.isUsed():
                count+=1
            else:
                progress_count+=3
                continue
            
            r=img.getData(asarray=True, ftype=self.ftype)
                        
            self.progress.setValue(progress_count)
            progress_count+=1

            if self.progressWasCanceled():
                return False

            if img.isRGB() and (r.shape[2]>3):
                r = r[...,0:3]
                
            r = self.calibrate(r, master_bias, master_dark, master_flat, hot_pixels, **args)
            
            if original_shape is None:
                original_shape = r.shape
            
            if self.progressWasCanceled():
                return False
            self.progress.setValue(progress_count)
            progress_count+=1
                               
            r = self.registerImages(img,r)

            if self.progressWasCanceled():
                return False
            self.progress.setValue(progress_count)
            progress_count+=1
            
            tmpfilelist.append(utils.storeTmpArray(r,self.temp_path,self.checked_compressed_temp==2))
        
        mdn=self._operationOnSubregions(operation,tmpfilelist,original_shape,name,256,256, **args)
        
        del tmpfilelist
        
        self.statusBar.clearMessage()
        
        return mdn
    
    def deGenerateLightCurves(self):
        return self.generateLightCurves()
    
    def generateLightCurves(self,method=None):
        
        del self._bas
        del self._drk
        del self._flt
                
        self._drk=None
        self._flt=None
        self._bas=None
        
        self.trace('generating light curves, please wait...')
        
        """
        selecting method and setting options
        before stacking
        """
        
        if(self.wnd.masterBiasCheckBox.checkState() == 2):
            self.stack_dlg.tabWidget.setTabEnabled(1,False)
            show1=False
        else:
            self.stack_dlg.tabWidget.setTabEnabled(1,True)
            show1=True
        
        if(self.wnd.masterDarkCheckBox.checkState() == 2):
            self.stack_dlg.tabWidget.setTabEnabled(2,False)
            show2=False
        else:
            self.stack_dlg.tabWidget.setTabEnabled(2,True)
            show2=True
            
        if(self.wnd.masterFlatCheckBox.checkState() == 2):
            self.stack_dlg.tabWidget.setTabEnabled(3,False)
            show3=False
        else:
            self.stack_dlg.tabWidget.setTabEnabled(3,True)
            show3=True
        
        if (show1 or show2 or show3):
            self.stack_dlg.tabWidget.setTabEnabled(0,False)
            if not(method is None):
                bias_method=method
                dark_method=method
                flat_method=method
                lght_method=method
            
                    
                bias_args={'lk':self.stack_dlg.biasLKappa.value(),
                            'hk':self.stack_dlg.biasHKappa.value(),
                            'iterations':self.stack_dlg.biasKIters.value(),
                            'debayerize_result':False}
                
                dark_args={'lk':self.stack_dlg.darkLKappa.value(),
                        'hk':self.stack_dlg.darkHKappa.value(),
                        'iterations':self.stack_dlg.darkKIters.value(),
                        'debayerize_result':False}
                
                flat_args={'lk':self.stack_dlg.flatLKappa.value(),
                        'hk':self.stack_dlg.flatHKappa.value(),
                        'iterations':self.stack_dlg.flatKIters.value(),
                        'debayerize_result':False}
                        
                lght_args={'lk':self.stack_dlg.ligthLKappa.value(),
                        'hk':self.stack_dlg.ligthHKappa.value(),
                        'iterations':self.stack_dlg.ligthKIters.value(),
                        'debayerize_result':True}
            elif self.stack_dlg.exec_():
                bias_method=self.stack_dlg.biasStackingMethodComboBox.currentIndex()
                dark_method=self.stack_dlg.darkStackingMethodComboBox.currentIndex()
                flat_method=self.stack_dlg.flatStackingMethodComboBox.currentIndex()
                lght_method=self.stack_dlg.ligthStackingMethodComboBox.currentIndex()
            
                    
                bias_args={'lk':self.stack_dlg.biasLKappa.value(),
                            'hk':self.stack_dlg.biasHKappa.value(),
                            'iterations':self.stack_dlg.biasKIters.value(),
                            'debayerize_result':False}
                
                dark_args={'lk':self.stack_dlg.darkLKappa.value(),
                        'hk':self.stack_dlg.darkHKappa.value(),
                        'iterations':self.stack_dlg.darkKIters.value(),
                        'debayerize_result':False}
                
                flat_args={'lk':self.stack_dlg.flatLKappa.value(),
                        'hk':self.stack_dlg.flatHKappa.value(),
                        'iterations':self.stack_dlg.flatKIters.value(),
                        'debayerize_result':False}
                        
                lght_args={'lk':self.stack_dlg.ligthLKappa.value(),
                        'hk':self.stack_dlg.ligthHKappa.value(),
                        'iterations':self.stack_dlg.ligthKIters.value(),
                        'debayerize_result':True}
            else:
                self.stack_dlg.tabWidget.setTabEnabled(0,True)
                return False
            self.stack_dlg.tabWidget.setTabEnabled(0,True)
            
        self.wnd.tabWidget.setCurrentIndex(2)
        self.wnd.chartsTabWidget.setCurrentIndex(1)
        self.wnd.saveADUChartPushButton.setEnabled(False)
        self.wnd.saveMagChartPushButton.setEnabled(False)
        self.wnd.chartsTabWidget.setTabEnabled(1,False)
        self.wnd.chartsTabWidget.setTabEnabled(2,False)
        self.wnd.aduListWidget.clear()
        self.wnd.magListWidget.clear()
        self.qapp.processEvents()
        
        self.lock()
        
        self.master_bias_file = str(self.wnd.masterBiasLineEdit.text())
        self.master_dark_file = str(self.wnd.masterDarkLineEdit.text())
        self.master_flat_file = str(self.wnd.masterFlatLineEdit.text())
        
        if (self.wnd.masterBiasCheckBox.checkState() == 2):
            if os.path.isfile(self.master_bias_file):
                bsa=utils.Frame(self.master_bias_file, **self.frame_open_args)
                self._bas=bas.getData(asarray=True, ftype=self.ftype)
            elif self.master_bias_file.replace(' ','').replace('\t','') == '':
                self.trace('skipping bias-frame calibration')
            else:
                msgBox = Qt.QMessageBox()
                msgBox.setText(tr("Cannot open \'"+self.master_bias_file+"\':"))
                msgBox.setInformativeText(tr("the file does not exist."))
                msgBox.setIcon(Qt.QMessageBox.Critical)
                msgBox.exec_()
                return False
        elif (len(self.biasframelist)>0):
            self.statusBar.showMessage(tr('Creating master-dark, please wait...'))
            _bas=self.getStackingMethod(bias_method,self.biasframelist, None, None, None, **dark_args)
            if _das is None:
                return False
            else:
                self._bas=_bas
        else:
            self.trace('skipping bias-frame calibration')
            
        if (self.wnd.masterDarkCheckBox.checkState() == 2):
            if os.path.isfile(self.master_dark_file):
                drk=utils.Frame(self.master_dark_file, **self.frame_open_args)
                self._drk=drk.getData(asarray=True, ftype=self.ftype)
            elif self.master_dark_file.replace(' ','').replace('\t','') == '':
                self.trace('skipping dark-frame calibration')
            else:
                utils.showErrorMsgBox(tr("Cannot open")+" \'"+self.master_dark_file+"\':",tr("the file does not exist."))
                return False
        elif (len(self.darkframelist)>0):
            self.statusBar.showMessage(tr('Creating master-dark, please wait...'))
            _drk=self.getStackingMethod(dark_method,self.darkframelist, None, None, None, **dark_args)
            if _drk is None:
                return False
            else:
                self._drk=_drk
        else:
            self.trace('skipping dark-frame calibration')
            
        if (self.wnd.masterFlatCheckBox.checkState() == 2):
            if os.path.isfile(self.master_flat_file):
                flt=utils.Frame(self.master_flat_file, **self.frame_open_args)
                self._flt=flt.getData(asarray=True, ftype=self.ftype)
            elif self.master_flat_file.replace(' ','').replace('\t','') == '':
                self.trace('skipping flatfield calibration')
            else:
                utils.showErrorMsgBox(tr("Cannot open")+" \'"+self.master_dark_file+"\':",tr("the file does not exist."))
                return False
            
        elif (len(self.flatframelist)>0):
            self.statusBar.showMessage(tr('Creating master-flat, please wait...'))
            _flt=self.getStackingMethod(flat_method,self.flatframelist, None, self._drk, None,**flat_args)
            if _flt is None:
                return False
            else:
                self._flt=_flt
        else:
            self.trace('skipping flatfield calibration')
 
        
        #create empty lightcurve dict
        self.lightcurve={True:{},False:{},'time':[],'info':[],'magnitudes':{}}
        self.progress.reset()     
        self.progress.setMaximum(len(self.framelist))
       
        cx=self.currentWidth/2.0
        cy=self.currentHeight/2.0
                
        count=0
        
        for i in self.starslist:
            self.lightcurve[i[6]][i[2]]={'magnitude':i[7],'data':[], 'error':[]}
            
            for comp in range(self.getNumberOfComponents()):
                self.addLightCurveListElement(str(i[2])+'-'+self.getComponentName(comp),
                                              str(i[2]),
                                              self.wnd.aduListWidget,
                                              i[6],
                                              count,
                                              16,
                                              checked=(not i[6]),
                                              component=comp)
            count+=1
            
            
        used_name_list=[]
        count=0
        
        self.use_image_time=(self.wnd.imageDateCheckBox.checkState()==2)
        
        master_bias, master_dark, master_flat, hot_pixels = self.generateMasters(self._bas,self._drk,self._flt)
        
        for img in self.framelist:
            count+=1
            if not (img.isUsed()):
                self.trace('\nskipping image '+str(img.name))
                continue
            else:
                self.trace('\nusing image '+str(img.name))
                
            self.progress.setValue(count)
            r = img.getData(asarray=True, ftype=self.ftype)
            r = self.calibrate(r, master_bias, master_dark, master_flat, hot_pixels, debayerize_result=True)
            
            if self.use_image_time:
                self.lightcurve['time'].append(img.getProperty('UTCEPOCH'))
            else:
                self.lightcurve['time'].append(count)
            
            for i in self.starslist:
                self.trace('computing adu value for star '+str(i[2]))
               
                di = dist(cx,cy,i[0],i[1])
                an = math.atan2((cy-i[1]),(cx-i[0]))
               
                an2=img.angle*math.pi/180.0
               
                strx = cx - di*math.cos(an+an2) + img.offset[0]
                stry = cy - di*math.sin(an+an2) + img.offset[1]
               
                if self.progressWasCanceled():
                    return False 
               
                try:
                    adu_val, adu_delta = utils.getStarMagnitudeADU(r,strx,stry,i[3],i[4],i[5])
                except Exception as exc:
                    utils.showErrorMsgBox(str(exc))
                    self.unlock()
                    return False
                   
               
                self.lightcurve[i[6]][i[2]]['data'].append(adu_val)
                self.lightcurve[i[6]][i[2]]['error'].append(adu_delta)

            self.wnd.aduLabel.repaint()
        

        #converting to ndarray
        for i in  self.lightcurve[False]:
            self.lightcurve[False][i]['data']=np.array(self.lightcurve[False][i]['data'],dtype=self.ftype)
            self.lightcurve[False][i]['error']=np.array(self.lightcurve[False][i]['error'],dtype=self.ftype)
        
        for i in  self.lightcurve[True]:
            self.lightcurve[True][i]['data']=np.array(self.lightcurve[True][i]['data'],dtype=self.ftype)
            self.lightcurve[True][i]['error']=np.array(self.lightcurve[True][i]['error'],dtype=self.ftype)
        
        self.wnd.saveADUChartPushButton.setEnabled(True)

        self.progress.setMaximum(len(self.lightcurve))
        
        count=0
        #now reference star will be used to compute the actual magnitude
        if len(self.lightcurve[True]) > 0:
            for i in  self.lightcurve[False]:
                
                star=self.lightcurve[False][i]
                magref=[]
                magerr=[]
                
                if (len(star['data'].shape)==2):
                    
                    bb=star['data'][:,2]
                    vv=star['data'][:,1]
                    
                    star_bv_index=-2.5*np.log10(bb/vv)
                    
                    star_bv_error=[]
                    
                    if len(star['error'])>0:
                        bd=star['error'][:,2]
                        vd=star['error'][:,1]
                        star_bv_error=2.5*(np.abs(bd/bb)+abs(vd/vv))
                        
                    star_bv_error=np.array(star_bv_error)
                    
                    self.lightcurve['magnitudes'][i+'(B-V)']={'data':star_bv_index, 'error':star_bv_error}
                    self.addLightCurveListElement(str(i+'(B-V)'),str(i+'(B-V)'),self.wnd.magListWidget,'magnitudes',count)
                    count+=1
                
                self.lightcurve['magnitudes'][i]={}
                
                for j in  self.lightcurve[True]:
                    ref = self.lightcurve[True][j]
                    if (len(star['data'].shape)==2) and (len(ref['data'].shape)==2):
                        
                        rbb=ref['data'][:,2]
                        rvv=ref['data'][:,1]
                        
                        ref_bv_index=-2.5*np.log10(rbb/rvv)                                                
                        ref_bv_error=[]
                        
                        if len(ref['error'])>0:
                            rbd=ref['error'][:,2]
                            rvd=ref['error'][:,1]
                            ref_bv_error=2.5*(np.abs(rbd/rbb)+abs(rvd/rvv))
                                
                        ref_bv_error=np.array(ref_bv_error)
                        
                        color_dif=0.1*(star_bv_index-ref_bv_index)
                        color_err=0.1*(star_bv_error+ref_bv_error)
                        
                        strval=star['data'].sum(1)
                        refval=ref['data'].sum(1)
                        
                        strerr=star['error'].sum(1)
                        referr=ref['error'].sum(1)
                        
                        magref.append(ref['magnitude']-2.5*np.log10(strval/refval)-color_dif)
                        magerr.append(2.5*(np.abs(strerr/strval)+abs(referr/refval))+color_err)
                    else:
                        
                        strval=star['data']
                        refval=ref['data']
                        
                        strerr=star['error']
                        referr=ref['error']
                        
                        magref.append(ref['magnitude']-2.5*np.log10(star['data']/ref['data']))
                        magerr.append(2.5*(np.abs(strerr/strval)+abs(referr/refval)))
                
                self.lightcurve['magnitudes'][i]['data']=np.array(magref).mean(0)
                self.lightcurve['magnitudes'][i]['error']=np.array(magerr).mean(0)
                self.addLightCurveListElement(str(i),str(i),self.wnd.magListWidget,'magnitudes',count,checked=True)
                count+=1

        self.fillNumericData()

        self.wnd.saveMagChartPushButton.setEnabled(True)
        self.wnd.chartsTabWidget.setTabEnabled(1,True)
        self.wnd.chartsTabWidget.setTabEnabled(2,True)
    
        self.unlock()
        
    
    def fillNumericData(self):
        
        n1 = len(self.lightcurve[False])
        n2 = len(self.lightcurve[True])
        n3 = len(self.lightcurve['magnitudes'])
        
        
        shape=self.lightcurve[False].values()[0]['data'].shape

        if len(shape)==2:
            ncomp = shape[1]
        else:
            ncomp = 1
        
        tot_cols = 2+(n1+n2)*ncomp+n3
            
        tot_rows = len(self.lightcurve['time'])
        
        hdr_lbls=['index','date']
        
        self.wnd.numDataTableWidget.clear()
        self.wnd.numDataTableWidget.setSortingEnabled(False)
        self.wnd.numDataTableWidget.setColumnCount(tot_cols)
        self.wnd.numDataTableWidget.setRowCount(tot_rows)
        
        row_count = 0
        for i in self.lightcurve['time']:
            idx_item=Qt.QTableWidgetItem('{0:04d}'.format(row_count+1))
            dte_item=Qt.QTableWidgetItem(str(i))
            self.wnd.numDataTableWidget.setItem(row_count,0,idx_item)
            self.wnd.numDataTableWidget.setItem(row_count,1,dte_item)
            row_count+=1
        
        col_count = 2
        for i in self.lightcurve[False]:
            if ncomp > 1:
                if ncomp==3:
                    hdr_lbls.append(str(i)+'-I (ADU)')
                    hdr_lbls.append(str(i)+'-V (ADU)')
                    hdr_lbls.append(str(i)+'-B (ADU)')
                else:
                    for c in xrange(ncomp):
                        hdr_lbls.append(str(i)+'-'+str(c)+' (ADU)')
                row_count=0
                for vl in self.lightcurve[False][i]['data']:
                    for v in vl:
                        val_item=Qt.QTableWidgetItem(str(v))
                        self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                        col_count+=1
                    col_count-=ncomp
                    row_count+=1
            else:
                hdr_lbls.append(str(i)+' (ADU)')
                row_count=0
                for v in self.lightcurve[False][i]['data']:
                    val_item=Qt.QTableWidgetItem(str(v))
                    self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                    row_count+=1
            col_count+=ncomp
            
        for i in self.lightcurve[True]:
            if ncomp > 1:
                if ncomp==3:
                    hdr_lbls.append(str(i)+'-I (ADU)')
                    hdr_lbls.append(str(i)+'-V (ADU)')
                    hdr_lbls.append(str(i)+'-B (ADU)')
                else:
                    for c in xrange(ncomp):
                        hdr_lbls.append(str(i)+'-'+str(c)+' (ADU)')
                row_count=0
                for vl in self.lightcurve[True][i]['data']:
                    for v in vl:
                        val_item=Qt.QTableWidgetItem(str(v))
                        self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                        col_count+=1
                    col_count-=ncomp
                    row_count+=1
            else:
                hdr_lbls.append(str(i)+' (ADU)')
                row_count=0
                for v in self.lightcurve[True][i]['data']:
                    val_item=Qt.QTableWidgetItem(str(v))
                    self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                    row_count+=1
            col_count+=ncomp
  
        for i in self.lightcurve['magnitudes']:
            hdr_lbls.append(str(i)+' (Mag)')
            row_count=0
            for v in self.lightcurve['magnitudes'][i]['data']:
                val_item=Qt.QTableWidgetItem(str(v))
                self.wnd.numDataTableWidget.setItem(row_count,col_count,val_item)
                row_count+=1
            col_count+=1
                    
        self.wnd.numDataTableWidget.setHorizontalHeaderLabels(hdr_lbls)
        self.wnd.numDataTableWidget.setSortingEnabled(True)
    
    def exportNumericDataCSV(self, val):
        file_name = str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the project"),
                                                os.path.join(self.current_dir,'lightcurves.csv'),
                                                "CSV *.csv (*.csv);;All files (*.*)",None,
                                                self._dialog_options))
        utils.exportTableCSV(self, self.wnd.numDataTableWidget, file_name, sep='\t', newl='\n')
        
    def addLightCurveListElement(self,name,obj_name,widget,index,points,smoothing=8,checked=False,component=0):
        q=Qt.QListWidgetItem(name,widget)
        q.setCheckState(2*checked)
        q.listindex=(index,obj_name,component)
        q.chart_properties={'color':self.getChartColor(component),
                            'line': False,
                            'points': self.getChartPoint(points),
                            'bars':'|',
                            'smoothing':smoothing,
                            'point_size':2,
                            'line_width':1}
        
    def levelsDialogButtonBoxClickedEvent(self, button):
        pushed = self.levels_dlg.buttonBox.standardButton(button)
        
        if pushed == self.levels_dlg.buttonBox.Reset:
            self.levels_dlg.dataClippingGroupBox.setChecked(False)
            self.resetLevels()
        elif pushed == self.levels_dlg.buttonBox.Apply:
            self.backUpLevels()
            self._stk=self.getNewLevels(self._old_stk)
            self.updateResultImage()
        elif pushed == self.levels_dlg.buttonBox.Discard:
            self.discardLevels()
            
    def resetLevels(self):
        self.levels_dlg.curveTypeComboBox.setCurrentIndex(0)
        self.levels_dlg.aDoubleSpinBox.setValue(0)
        self.levels_dlg.bDoubleSpinBox.setValue(1)
        self.levels_dlg.oDoubleSpinBox.setValue(1)
        self.levels_dlg.mDoubleSpinBox.setValue(1)
        self.levels_dlg.nDoubleSpinBox.setValue(np.e)
        for name in self.MWB_CORRECTION_FACTORS:
            self.MWB_CORRECTION_FACTORS[name]=[0,0.5,1]
        self.updateMWBControls()
        self.updateHistograhm2()

    def discardLevels(self):
        self.levels_dlg.curveTypeComboBox.setCurrentIndex(self._old_funcidx)
        self.levels_dlg.aDoubleSpinBox.setValue(self._old_a)
        self.levels_dlg.bDoubleSpinBox.setValue(self._old_b)
        self.levels_dlg.oDoubleSpinBox.setValue(self._old_o)
        self.levels_dlg.mDoubleSpinBox.setValue(self._old_m)
        self.levels_dlg.nDoubleSpinBox.setValue(self._old_n)        
        self.updateHistograhm2()

        
    def backUpLevels(self):
        self._old_funcidx = self.levels_dlg.curveTypeComboBox.currentIndex()
        self._old_a = float(self.levels_dlg.aDoubleSpinBox.value())
        self._old_b = float(self.levels_dlg.bDoubleSpinBox.value())
        self._old_o = float(self.levels_dlg.oDoubleSpinBox.value())
        self._old_m = float(self.levels_dlg.mDoubleSpinBox.value())
        self._old_n = float(self.levels_dlg.nDoubleSpinBox.value())
    
    def editLevels(self):
        
        self.backUpLevels()

        self.rebuildMWBControls()
                
        if self._old_stk is None:
            self._oldhst=self._hst.copy()
            self._old_stk=self._stk.copy()
            self.resetLevels()
        
        self.updateHistograhm2()
        
        if self.levels_dlg.exec_()==1:
            self._stk=self.getNewLevels(self._old_stk)
        
        self.clearMWBControls()
        self.updateResultImage()
        
    def getLevelsClippingRange(self):
        if self.levels_dlg.dataClippingGroupBox.isChecked():
            if self.levels_dlg.dataClipping8BitRadioButton.isChecked():
                data_max = 255
                data_min = 0
            elif self.levels_dlg.dataClipping16BitRadioButton.isChecked():
                data_max = 65535
                data_min = 0
        else:
            data_max = None
            data_min = None
        return (data_min,data_max)
    
    def getNewLevels(self, data):
        
        A = float(self.levels_dlg.aDoubleSpinBox.value())
        B = float(self.levels_dlg.bDoubleSpinBox.value())
        o = float(self.levels_dlg.oDoubleSpinBox.value())
        m = float(self.levels_dlg.mDoubleSpinBox.value())
        n = float(self.levels_dlg.nDoubleSpinBox.value())    
        
        cf=[]
        
        for i in self.component_table:
            if self.levels_dlg.MWBGroupBox.isChecked():
                cf.append(self.MWB_CORRECTION_FACTORS[self.component_table[i]])
            else:
                cf.append(1.0)
        
        if self.levels_dlg.MWBGroupBox.isChecked():
            data=utils.applyWhiteBalance(data,
                                         self.MWB_CORRECTION_FACTORS,
                                         self.component_table)
        
        if self.levelfunc_idx == 0: #linear
            data = A+B*data
        elif self.levelfunc_idx == 1: #logarithmic
            data = A+B*np.emath.logn(n,(o+m*data))
        elif self.levelfunc_idx == 2: #power
            data = A+B*((o+m*data)**n)
        elif self.levelfunc_idx == 3: #exponential
            data = A+B*(n**(o+m*data))

        if self.levels_dlg.dataClippingGroupBox.isChecked():
            if self.levels_dlg.dataClipping8BitRadioButton.isChecked():
                data_max = 255
                data_min = 0
            elif self.levels_dlg.dataClipping16BitRadioButton.isChecked():
                data_max = 65535
                data_min = 0
                
            return data.clip(data_min,data_max)
        else:
            return data
    
    def updateHistograhm(self, curve_idx):
        
        if self._ignore_histogrham_update:
            return
        
        scenablied = self.levels_dlg.dataClippingGroupBox.isChecked()
        clipping   = scenablied and self.levels_dlg.dataClippingClipDataRadioButton.isChecked()
        streching  = scenablied and self.levels_dlg.dataClippingFitDataRadioButton.isChecked()
                
        A = float(self.levels_dlg.aDoubleSpinBox.value())
        B = float(self.levels_dlg.bDoubleSpinBox.value())
        o = float(self.levels_dlg.oDoubleSpinBox.value())
        m = float(self.levels_dlg.mDoubleSpinBox.value())
        n = float(self.levels_dlg.nDoubleSpinBox.value())
    
        self.levelfunc_idx=curve_idx
        
        data_min,data_max = self.getLevelsClippingRange()
        
        if streching:
            if curve_idx == 0: #linear
                tmphst=self._oldhst[0,1]
            elif curve_idx == 1: #logarithmic
                tmphst=np.emath.logn(n,(o+m*self._oldhst[0,1]))
            elif curve_idx == 2: #power
                tmphst=((o+m*self._oldhst[0,1])**n)
            elif curve_idx == 3: #exponential
                tmphst=(n**(o+m*self._oldhst[0,1]))
            
            minh = min(tmphst)
            maxh = max(tmphst)
            
            B = (data_max-data_min)/(maxh-minh)
            A = -(data_max-data_min)*minh/(maxh-minh)
            
            self._ignore_histogrham_update = True
            self.levels_dlg.aDoubleSpinBox.setValue(A)
            self.levels_dlg.bDoubleSpinBox.setValue(B)
            self._ignore_histogrham_update = False
    
        if self.levels_dlg.histoTabWidget.currentIndex() == 0:
            self._hst[0,0]=np.zeros_like(self._hst[0,0])
            
            if self.levels_dlg.MWBGroupBox.isChecked():
                _hst_wb=utils.applyHistWhiteBalance(self._oldhst,
                                                    self.MWB_CORRECTION_FACTORS,
                                                    self.component_table)
            else:
                _hst_wb=self._oldhst
            
            for i in range(len(self._hst)):
                
                if curve_idx == 0: #linear
                    self._hst[i,1]=A+B*_hst_wb[i,1]
                elif curve_idx == 1: #logarithmic
                    self._hst[i,1]=A+B*np.emath.logn(n,(o+m*_hst_wb[i,1]))
                elif curve_idx == 2: #power
                    self._hst[i,1]=A+B*((o+m*_hst_wb[i,1])**n)
                elif curve_idx == 3: #exponential
                    self._hst[i,1]=A+B*(n**(o+m*_hst_wb[i,1]))
                
                if i > 0:
                                            
                    if clipping:
                        mask = (self._hst[i,1]>=data_min)*(self._hst[i,1]<=data_max)
                        self._hst[i,0]=_hst_wb[i,0]*mask[:-1]
                    else:
                        self._hst[i,0]=_hst_wb[i,0]
                    
                    for j in range(len(self._hst[i,0])):
                        x = self._hst[i,1][j]
                        try:
                            k=np.argwhere(self._hst[0,1]>=x)[0,0]
                            x1=self._hst[0,1][k-1]
                            x2=self._hst[0,1][k]
                            
                            # x1 <= x < x2
                            
                            delta=x2-x1

                            self._hst[0,0][k-1]+=self._hst[i,0][j]*(x2-x)/delta
                            self._hst[0,0][k]+=self._hst[i,0][j]*(x-x1)/delta
                        except:
                            pass
            
        elif self.levels_dlg.histoTabWidget.currentIndex() == 1:
            self._preview_image=utils.arrayToQImage(self.getNewLevels(self._preview_data),
                                                    bw_jet=self.use_colormap_jet,
                                                    levels_range=self.levels_range)
            
        self.levels_dlg.update()
        
        
    def updateHistograhm2(self, *arg,**args):
        self.updateHistograhm(self.levelfunc_idx)
        
    def progressWasCanceled(self):
        self.qapp.processEvents()

        if self.wasCanceled:
            self.wasCanceled=False
            self.progress.hide()
            self.progress.reset()
            self.cancelProgress.hide()
            self.statusBar.showMessage(tr('Operation canceled by user'))
            self.unlock()
            return True
        else:
            return False

    def getDestDir(self):
        destdir = str(Qt.QFileDialog.getExistingDirectory(self.wnd,
                                                          tr("Choose the output folder"),
                                                          self.current_dir,
                                                          self._dialog_options | Qt.QFileDialog.ShowDirsOnly ))
        self.save_dlg.lineEditDestDir.setText(str(destdir))
        
        
    
    def saveVideo(self):
        
        file_name = str(Qt.QFileDialog.getSaveFileName(self.wnd, tr("Save the project"),
                                                       os.path.join(self.current_dir,'Untitled.avi'),
                                                       "Video *.avi (*.avi);;All files (*.*)",None,
                                                       self._dialog_options))
        
        if file_name.replace(' ','') == '':
            self.trace('no video file selected for output') 
            return False
        
        
        self.video_dlg.exec_()
        
        cidx = self.video_dlg.codecComboBox.currentIndex()
        custom_size = (self.video_dlg.fullFrameCheckBox.checkState()==0)
        fps=self.video_dlg.fpsSpinBox.value()
        size=(self.currentWidth,self.currentHeight)
        fitlvl=(self.video_dlg.fitVideoCheckBox.checkState()==2)
        
        fh = self.video_dlg.resSpinBox.value()
        
        if cidx==0:
            fcc_str='DIVX'
            max_res=(4920,4920)
        elif cidx==0:
            fcc_str='MJPG'
            max_res=(9840,9840)
        elif cidx==0:
            fcc_str='U263'
            max_res=(2048,1024)
                    
        if not custom_size:
            size=(self.currentWidth,self.currentHeight)    
        else:
            fzoom=float(fh)/float(self.currentHeight)
            fw=int(self.currentWidth*fzoom)
            size=(fw,fh)
        
        try:
            vw=cv2.VideoWriter(file_name,cv2.cv.CV_FOURCC(*fcc_str),fps,size)
        except Exception as exc:
            estr=str(exc)
            if ('doesn\'t support this codec' in estr):
                self.trace('\n It seems that opencv cannot handle this format.')
                self.trace(' Try to use a lower resolution and assure you\nhave the permissions to write the file.')
                
                utils.showErrorMsgBox(tr("Cannot create the video file."),
                                      tr("Try to use a lower resolution and assure you\nhave the permissions to write the file."))                
        
        self.trace('writing video to: \"'+file_name+'\"')
        self.trace(' FPS : ' + str(fps))
        self.trace(' FOURCC : ' + fcc_str)
        self.trace(' FRAME SIZE : ' + str(size))
        
        
        
        if vw.isOpened():
            self.lock(False)
            self.progress.setMaximum(len(self.framelist))
            count=0
            self.statusBar.showMessage(tr('Writing video, please wait...'))
            
            
            for frm in self.framelist:
                count+=1
                self.qapp.processEvents()
                self.progress.setValue(count)
                if frm.isUsed():
                    
                    self.trace('\nusing frame '+str(frm.name))
                    self.trace(' loading data...')
                    
                    img = self.debayerize(frm.getData(asarray=True, asuint8=True, fit_levels=fitlvl)).astype(np.uint8)
                    
                    _rgb = (len(img.shape) == 3)
                    
                    if self.video_dlg.useAligedCheckBox.checkState()==2:
                        img = self.registerImages(frm,img)
                    
                    if custom_size:
                        self.trace('resizing image to ' + str(size))
                        if _rgb:
                            img = sp.ndimage.interpolation.zoom(img,(fzoom,fzoom,1),order=self.interpolation_order)
                        else:
                            img = sp.ndimage.interpolation.zoom(img,(fzoom,fzoom),order=self.interpolation_order)
                    
                    if _rgb:
                        cv2img = np.empty_like(img)
                        self.trace(' converting to BRG format...')
                        cv2img[...,0]=img[...,2]
                        cv2img[...,1]=img[...,1]
                        cv2img[...,2]=img[...,0]
                    else:
                        self.trace(' converting to BRG format...')
                        if self.use_colormap_jet:
                            img = utils.getJetColor(img,fitlvl)
                            cv2img = np.empty((size[1],size[0],3),dtype=np.uint8)
                            cv2img[...,0]=img[2]
                            cv2img[...,1]=img[1]
                            cv2img[...,2]=img[0]
                        else:
                            cv2img = np.empty((size[1],size[0],3),dtype=np.uint8)
                            cv2img[...,0]=img[...]
                            cv2img[...,1]=img[...]
                            cv2img[...,2]=img[...]
                            
                    self.trace(' pushing frame...')
                    
                    vw.write(cv2img)
                    
                    del cv2img
                    
                else:
                    self.trace('\nskipping frame '+str(frm.name))
                    
            vw.release()
            self.unlock()
            self.statusBar.showMessage(tr('DONE'))
            self.trace('\nDONE')
            
        else:
            self.trace('\nCannot open destination file')
        
    def saveResult(self):
        self.updateSaveOptions()
        if self.save_dlg.exec_() != 1:
            return False
        destdir=str(self.save_dlg.lineEditDestDir.text())
        
        while not os.path.isdir(destdir):
            utils.showWarningMsgBox(tr("The selected output folder is not a directory\nor it does not exist!"))
            if self.save_dlg.exec_() != 1:
                return False
            destdir=str(self.save_dlg.lineEditDestDir.text())

        self.lock()
        self.qapp.processEvents()
        name=str(self.save_dlg.lineEditFileName.text())

        if self.save_dlg.radioButtonJpeg.isChecked():
            frmat='jpg'
        elif self.save_dlg.radioButtonPng.isChecked():
            frmat='png'
        elif self.save_dlg.radioButtonTiff.isChecked():
            frmat='tiff'
        elif self.save_dlg.radioButtonFits.isChecked():
            frmat='fits'
        elif self.save_dlg.radioButtonNumpy.isChecked():
            frmat='numpy'
        
        if self.save_dlg.radioButton8.isChecked():
            bits=8
        elif self.save_dlg.radioButton16.isChecked():
            bits=16
        elif self.save_dlg.radioButton32.isChecked():
            bits=32
        elif self.save_dlg.radioButton64.isChecked():
            bits=64
        
        if self.save_dlg.radioButtonInt.isChecked():
            if self.save_dlg.checkBoxUnsigned.checkState()==2:
                dtype='uint'
            else:
                dtype='int'
        elif self.save_dlg.radioButtonFloat.isChecked():
            dtype='float'
            
        if frmat=='fits':
            self._save_fits(destdir,name,bits)
        elif frmat=='numpy':
            self._save_numpy(destdir,name,bits,dtype)
        else:
            self._save_cv2(destdir,name,frmat,bits)
        
        self.unlock()
        
    def _save_fits(self,destdir, name, bits):

        rgb_mode = (self.save_dlg.rgbFitsCheckBox.checkState()==2)
        fits_compressed = (self.save_dlg.comprFitsCheckBox.checkState()==2)
        
        avg_name=os.path.join(destdir,name)
        frm = utils.Frame(avg_name)
        
        try:
            frm._imwrite_fits_(self._stk,rgb_mode,compressed=fits_compressed,outbits=bits)
        except:
            frm._imwrite_fits_(self._stk,rgb_mode,compressed=False,outbits=bits)
            utils.showWarningMsgBox(tr("Cannot save compressed files with this version of pyfits")+":\n "+ tr("the image was saved as an uncompressed FITS file."))
            
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if not(self._bas is None):
                bas_name=os.path.join(destdir,name+"-master-bias")
                frm = utils.Frame(bas_name)
                try:
                    frm._imwrite_fits_(self._bas,rgb_mode,compressed=fits_compressed,outbits=bits)
                except:
                    frm._imwrite_fits_(self._bas,rgb_mode,compressed=False,outbits=bits)
            if not(self._drk is None):
                drk_name=os.path.join(destdir,name+"-master-dark")
                frm = utils.Frame(drk_name)
                try:
                    frm._imwrite_fits_(self._drk,rgb_mode,compressed=fits_compressed,outbits=bits)
                except:
                    frm._imwrite_fits_(self._drk,rgb_mode,compressed=False,outbits=bits)
            if not(self._flt is None):
                flt_name=os.path.join(destdir,name+"-master-flat")
                frm = utils.Frame(flt_name)
                try:
                    frm._imwrite_fits_(self._flt,rgb_mode,compressed=fits_compressed,outbits=bits)
                except:
                    frm._imwrite_fits_(self._flt,rgb_mode,compressed=False,outbits=bits)
        del frm
        
    def _save_numpy(self,destdir, name, bits):

        #header = pyfits

        if bits==32:
            outbits=np.float32
        elif bits==64:
            outbits=np.float64
        
        avg_name=os.path.join(destdir,name)
        np.save(avg_name,self._stk.astype(outbits))
        
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if not(self._bas is None):
                bas_name=os.path.join(destdir,name+"-master-bias")
                np.save(bas_name,self._bas.astype(outbits))
                
            if not(self._drk is None):
                drk_name=os.path.join(destdir,name+"-master-dark")
                np.save(drk_name,self._drk.astype(outbits))
            
            if not(self._flt is None):
                flt_name=os.path.join(destdir,name+"-master-flat")
                np.save(flt_name,self._flt.astype(outbits))
    
    def _save_cv2(self,destdir, name, frmt, bits):
               
        if bits==8:
            rawavg=utils.normToUint8(self._stk, False)
            rawbas=utils.normToUint8(self._bas, False)
            rawdrk=utils.normToUint8(self._drk, False)
            rawflt=utils.normToUint8(self._flt, False)
        elif bits==16:
            rawavg=utils.normToUint16(self._stk, False)
            rawbas=utils.normToUint16(self._bas, False)
            rawdrk=utils.normToUint16(self._drk, False)
            rawflt=utils.normToUint16(self._flt, False)
        else:
            #this should never be executed!
            utils.showErrorMsgBox(tr("Cannot save image:"),tr("Unsupported format ")+str(bits)+"-bit "+tr("for")+" "+str(frmt))
            return False
                
        avg_name=os.path.join(destdir,name+"."+frmt)
        
        if frmt=='jpg':
            flags=(cv2.cv.CV_IMWRITE_JPEG_QUALITY,int(self.save_dlg.spinBoxIQ.value()))
        elif frmt=='png':
            flags=(cv2.cv.CV_IMWRITE_PNG_COMPRESSION,int(self.save_dlg.spinBoxIC.value()))
        else:
            flags=None
        
        frm = utils.Frame(avg_name)
        
        if not frm._imwrite_cv2_(rawavg,flags):
            return False
        
        
        if self.save_dlg.saveMastersCheckBox.checkState()==2:
            if not(self._bas is None):
                bas_name=os.path.join(destdir,name+"-master-bias."+frmt)
                frm = utils.Frame(bas_name)
                frm._imwrite_cv2_(rawbas,flags)
                
            if not(self._drk is None):
                drk_name=os.path.join(destdir,name+"-master-dark."+frmt)
                frm = utils.Frame(drk_name)
                frm._imwrite_cv2_(rawdrk,flags)
            
            if not(self._flt is None):
                flt_name=os.path.join(destdir,name+"-master-flat."+frmt)
                frm = utils.Frame(flt_name)
                frm._imwrite_cv2_(rawflt,flags)

        del frm

        