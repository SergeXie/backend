import os
import glob
import importlib
import sys


def reload_strategies():
    # 清除之前的策略字典（如果有的话）
    global my_dict
    my_dict = {}

    # 获取当前文件夹的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))

    if hasattr(sys, '_MEIPASS'):
        current_dir = current_dir.replace("\\dist\\main\\_internal", "")
        base_dir = current_dir.replace("\\utils\\strategys", "")
        sys.path.append(base_dir)
    # # 获取所有的py文件，排除__init__.py本身
    modules = glob.glob(os.path.join(current_dir, "*.py"))
    modules = [os.path.basename(f)[:-3] for f in modules if os.path.isfile(f) and not f.endswith('__init__.py')]

    # 动态导入每个模块并构建my_dict
    for module in modules:
        mod = importlib.import_module(f"utils.strategys.{module}")
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if callable(obj) and hasattr(obj, '__module__') and obj.__module__ == f"utils.strategys.{module}":
                my_dict[f"{module}.{attr}"] = obj
    return my_dict

# reload_strategies()
# print(my_dict)
