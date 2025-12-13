import torch
import sys
print(f'Python: {sys.version}')
print(f'Torch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')
try:
    import tensorflow
    print(f'TensorFlow: {tensorflow.__version__}')
except ImportError:
    print('TensorFlow: Not installed (Good)')

