# main.py

import simulation_engine
import view
import threading



def main():
    simulation = simulation_engine.SimulationEngine()
    view.global_data = simulation.visualization_data
    # 启动模拟引擎
    simulation_thread = threading.Thread(target=simulation.run_simulation)
    simulation_thread.start()
        # 启动Flask服务器
    view.app.run()
    simulation_thread.join()  # 等待模拟引擎完成初始化



if __name__ == '__main__':
    main()
