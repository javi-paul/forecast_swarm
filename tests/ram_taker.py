import gc
import time
import sys

large_list = []
while True:
    try:
        large_list.append([0] * (10**6))
        time.sleep(1)
    except KeyboardInterrupt:
        large_list.clear()
        del large_list
        gc.collect()
        print("RAM freed")
        sys.exit()
