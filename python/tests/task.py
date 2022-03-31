import undr.task

if __name__ == "__main__":
    with undr.task.ProcessManager(workers=1, priority_levels=2) as process_manager:
        pass
