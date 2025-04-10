# main.py
import tkinter as tk
from notebook_engine import NotebookEngine
from notebook_ui import NotebookUI, ConnectionManager

class NotebookApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modular Notebook Application")
        self.conn_manager = ConnectionManager(self.root)
        self.engine = NotebookEngine()
        self.notebook_ui = NotebookUI(self.root, self.engine)

if __name__ == "__main__":
    root = tk.Tk()
    app = NotebookApp(root)
    root.mainloop()

