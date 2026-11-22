"""Build, lint and test interactive PDFs: games, quizzes and teaching demos (AcroForm fields + JavaScript) for Chrome's PDF viewer."""
from .build import LivePdf
from .inspect import GameDoc, load
from .lint import lint
from .sim import Sim, SimError

__all__ = ['LivePdf', 'GameDoc', 'load', 'lint', 'Sim', 'SimError']
__version__ = '0.1.0'
