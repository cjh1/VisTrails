from core.configuration import ConfigurationObject

name = "SAHM"
identifier = "gov.usgs.sahm"
version = '0.0.2'

sahm_path = None
models_path = None
configuration = \
    ConfigurationObject(sahm_path='/vistrails/local_packages/sahm/SAHM',
                        models_path='/vistrails/local_packages/sahm/SAHM/Resources/ModelBuilder')
