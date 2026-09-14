#########-----------------------------WINDOWS-------------------------------#################################
from pathlib import Path
import numpy as np
from distutils.core import Extension, setup
from Cython.Build import cythonize

ext = [
    Extension('simulation.core.base', ['simulation/core/base.pyx']),
    Extension('simulation.core.entity', ['simulation/core/entity.pyx']),
    Extension('simulation.core.message', ['simulation/core/message.pyx']),
    Extension('simulation.core.arch', ['simulation/core/arch.pyx']),
    Extension('simulation.core.base_engine', ['simulation/core/base_engine.pyx']),
]

setup(
    name='core',
    ext_modules=cythonize(ext, language_level=3),
)

ext_arsenal = [
    Extension('simulation.arsenal.motor', ['simulation/arsenal/motor.pyx']),
    Extension('simulation.arsenal.radar', ['simulation/arsenal/radar.pyx'])
]
setup(
    name='asenal',
    ext_modules=cythonize(ext_arsenal, language_level=3),
)

