
# Import base class module
from pvrepresentationbase import *
from pvcdmsreader import *

# Import registry
from core.modules.module_registry import get_module_registry

# Import paraview
import paraview.simple as pvsp

# CDAT
import cdms2, cdtime, cdutil, MV2

class PVContourRepresentation(PVRepresentationBase):
    def __init__(self):
        PVRepresentationBase.__init__(self)
        self.contour_var_name = None
        self.contour_var_type = None
        self.contour_values = None
        self.time_range = {}

    def compute(self):
        # TODO:
        pass

    def set_contour_values(self, values):
        self.contour_values = values

    def set_contour_by(self, name, type):
        self.contour_var_name = name
        self.contour_var_type = type

    def execute(self):
        for cdms_var in self.cdms_variables:            
            reader = PVCDMSReader()
            time_values = [None, 1, True]
            image_data = reader.convert(cdms_var, time=time_values)

            #make white box filter so we can work at proxy level
            ProgrammableSource1 = pvsp.ProgrammableSource()
            
            #get a hole of the vtk level filter it controls
            ps = ProgrammableSource1.GetClientSideObject()
            
            #give it some data (ie the imagedata)            
            ps.myid = image_data
            
            ProgrammableSource1.OutputDataSetType = 'vtkImageData'
            ProgrammableSource1.PythonPath = ''

#            #make the scripts that it runs in pipeline RI and RD passes
            ProgrammableSource1.ScriptRequestInformation = """
executive = self.GetExecutive()
outInfo = executive.GetOutputInformation(0)
extents = self.myid.GetExtent()
outInfo.Set(executive.WHOLE_EXTENT(), extents[0], extents[1], extents[2], extents[3], extents[4], extents[5])
outInfo.Set(vtk.vtkDataObject.SPACING(), 1, 1, 1)
dataType = 10 # VTK_FLOAT
numberOfComponents = 1
vtk.vtkDataObject.SetPointDataActiveScalarInfo(outInfo, dataType, numberOfComponents)"""

            ProgrammableSource1.Script = """self.GetOutput().ShallowCopy(self.myid)"""            
            ProgrammableSource1.UpdatePipeline()            
            pvsp.SetActiveSource(ProgrammableSource1)
            
            contour = pvsp.Contour()
            pvsp.SetActiveSource(contour)
            
            self.contour_var_name = str(cdms_var.varNameInFile)
            contour.ContourBy = ['POINTS', self.contour_var_name]
            self.contour_values = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
            contour.Isosurfaces = self.contour_values
            
            contour.ComputeScalars = 1
            contour.ComputeNormals = 0
            contour.UpdatePipeline()
            
            contour_rep = pvsp.Show(view=self.view)

            # @todo: Remove hard-coded look-up table
            contour_rep.LookupTable = pvsp.GetLookupTableForArray(self.contour_var_name, 1, NanColor=[0.25, 0.0, 0.0], RGBPoints=[0.0, 0.23, 0.299, 0.754, 30.0, 0.706, 0.016, 0.15], VectorMode='Magnitude', ColorSpace='Diverging', LockScalarRange=1)
            
            # @todo: Remove hard-coded representation type
            contour_rep.Representation = 'Surface'
            contour_rep.ColorArrayName = self.contour_var_name

        for var in self.variables:
            reader = var.get_reader()
            self.contour_var_name = var.get_variable_name()
            self.contour_var_type = var.get_variable_type()

            # Update pipeline
            reader.UpdatePipeline()
            pvsp.SetActiveSource(reader)

            # Unroll a sphere
            # FIXME: Currently hard coded
            if reader.__class__.__name__ == 'UnstructuredNetCDFPOPreader':
                trans_filter = self.get_project_sphere_filter()
                pvsp.SetActiveSource(trans_filter)

            # Create a contour representation
            contour = pvsp.Contour()
            pvsp.SetActiveSource(contour)
            contour.ContourBy = [self.contour_var_type, self.contour_var_name]
            contour.Isosurfaces = self.contour_values

            # FIXME:
            # Hard coded for now
            contour.ComputeScalars = 1
            contour.ComputeNormals = 0
            contour_rep = pvsp.Show(view=self.view)

            # FIXME:
            # Hard coded for now
            contour_rep.LookupTable = pvsp.GetLookupTableForArray(self.contour_var_name, 1, NanColor=[0.25, 0.0, 0.0], RGBPoints=[0.0, 0.23, 0.299, 0.754, 30.0, 0.706, 0.016, 0.15], VectorMode='Magnitude', ColorSpace='Diverging', LockScalarRange=1)

            # FIXME:
            # Hard coded for now
            #contour_rep.Scale = [1, 1, 0.01]    

            # FIXME:
            # Hard coded for now
            contour_rep.Representation = 'Surface'
            contour_rep.ColorArrayName = self.contour_var_name

    @staticmethod
    def name():
        return 'PV Contour Representation'

    @staticmethod
    def configuration_widget(parent, rep_module):
        return ContourRepresentationConfigurationWidget(parent, rep_module)

class ContourRepresentationConfigurationWidget(RepresentationBaseConfigurationWidget):
    def __init__(self, parent, rep_module):
        RepresentationBaseConfigurationWidget.__init__(self, parent, rep_module)
        self.representation_module = parent
        layout = QVBoxLayout()
        self.setLayout(layout)

        sliceOffsetLayout = QHBoxLayout()
        sliceOffsetLabel = QLabel("Some property:")
        self.slice_offset_value =  QLineEdit (parent)
        sliceOffsetLayout.addWidget( sliceOffsetLabel )
        sliceOffsetLayout.addWidget( self.slice_offset_value )
        layout.addLayout(sliceOffsetLayout)
        parent.connect(self.slice_offset_value, SIGNAL("editingFinished()"), parent.stateChanged)

    def okTriggered(self, checked = False):
        """ okTriggered(checked: bool) -> None
        Update vistrail controller (if necessary) then close the widget

        """

def register_self():
    registry = get_module_registry()
    registry.add_module(PVContourRepresentation)
    registry.add_output_port(PVContourRepresentation, "self", PVContourRepresentation)
