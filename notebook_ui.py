# notebook_ui.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import socket
import json

# ----- ConnectionManager Class -----
class ConnectionManager:
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.connections = {}  # Dictionary to store connection info.
        self.active_connection = None
        self.setup_ui()

    def setup_ui(self):
        self.frame = ttk.Frame(self.parent_frame)
        self.frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        ttk.Label(self.frame, text="Server Connections", font=("Arial", 10, "bold")).pack(pady=2)
        self.listbox = tk.Listbox(self.frame, height=4)
        self.listbox.pack(fill=tk.X, padx=5)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Add Connection", command=self.add_connection).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove Connection", command=self.remove_connection).pack(side=tk.LEFT, padx=2)

    def add_connection(self):
        # Dialog to add a new connection.
        dialog = tk.Toplevel(self.parent_frame)
        dialog.title("Add Server Connection")
        ttk.Label(dialog, text="Server IP:").grid(row=0, column=0, padx=5, pady=5)
        ip_entry = ttk.Entry(dialog)
        ip_entry.insert(0, "127.0.0.1")
        ip_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Port:").grid(row=1, column=0, padx=5, pady=5)
        port_entry = ttk.Entry(dialog)
        port_entry.insert(0, "8080")
        port_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Username:").grid(row=2, column=0, padx=5, pady=5)
        username_entry = ttk.Entry(dialog)
        username_entry.grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Password:").grid(row=3, column=0, padx=5, pady=5)
        password_entry = ttk.Entry(dialog, show="*")
        password_entry.grid(row=3, column=1, padx=5, pady=5)
        status_label = ttk.Label(dialog, text="", foreground="red")
        status_label.grid(row=4, column=0, columnspan=2)

        def connect():
            ip = ip_entry.get()
            try:
                port = int(port_entry.get())
            except ValueError:
                status_label.config(text="Invalid port.")
                return
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            if not username or not password:
                status_label.config(text="Username and password required.")
                return
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((ip, port))
            except Exception as e:
                status_label.config(text=f"Connection failed: {e}")
                return
            try:
                payload = {"action": "login", "username": username, "password": password}
                s.send(json.dumps(payload).encode())
                response = json.loads(s.recv(1024).decode())
                if response.get("status") == "success":
                    token = response.get("token", "")
                    connection_name = f"{username}@{ip}:{port}"
                    self.connections[connection_name] = {"socket": s, "token": token}
                    self.listbox.insert(tk.END, connection_name)
                    status_label.config(text="Connected!")
                    dialog.destroy()
                else:
                    status_label.config(text=response.get("message", "Login failed"))
                    s.close()
            except Exception as e:
                status_label.config(text=f"Login error: {e}")
                s.close()

        ttk.Button(dialog, text="Connect", command=connect).grid(row=5, column=0, columnspan=2, pady=5)

    def remove_connection(self):
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            connection_name = self.listbox.get(index)
            conn_info = self.connections.pop(connection_name, None)
            if conn_info and conn_info.get("socket"):
                try:
                    conn_info["socket"].close()
                except Exception:
                    pass
            self.listbox.delete(index)
            if self.active_connection == connection_name:
                self.active_connection = None
        else:
            messagebox.showwarning("Remove Connection", "No connection selected.")

    def on_select(self, event):
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            self.active_connection = self.listbox.get(index)


# ----- NotebookUI Class -----
class NotebookUI:
    def __init__(self, root, engine):
        self.root = root
        self.engine = engine
        self.current_theme = "light"  # possible values: "light" or "dark"
        self.cells_ui = []  # list to store cell UI dictionaries
        self.setup_menu()
        self.setup_toolbar()
        self.setup_main_area()
        # Apply the initial theme.
        self.apply_theme()

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        # --- File Menu ---
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Notebook", command=self.new_notebook)
        file_menu.add_command(label="Open Notebook", command=self.open_notebook)
        file_menu.add_command(label="Save Notebook", command=self.save_notebook)
        file_menu.add_command(label="Save a Copy", command=self.save_copy)
        file_menu.add_separator()
        file_menu.add_command(label="Download as .ipynb", command=self.download_notebook)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        # --- Edit Menu ---
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self.undo_action)
        edit_menu.add_command(label="Redo", command=self.redo_action)
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=self.cut_action)
        edit_menu.add_command(label="Copy", command=self.copy_action)
        edit_menu.add_command(label="Paste", command=self.paste_action)
        # --- Insert Menu ---
        insert_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Insert", menu=insert_menu)
        insert_menu.add_command(label="Insert Code Cell", command=self.add_code_cell)
        insert_menu.add_command(label="Insert Markdown Cell", command=self.add_markdown_cell)
        # --- Runtime Menu ---
        runtime_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Runtime", menu=runtime_menu)
        runtime_menu.add_command(label="Run Current Cell", command=self.run_current_cell)
        runtime_menu.add_command(label="Run All Cells", command=self.run_all_cells)
        runtime_menu.add_separator()
        runtime_menu.add_command(label="Restart Runtime", command=self.restart_runtime)
        runtime_menu.add_command(label="Change Runtime Type", command=self.change_runtime_type)
        # --- Tools Menu ---
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Table of Contents", command=self.show_table_of_contents)
        tools_menu.add_command(label="Clear All Outputs", command=self.clear_all_outputs)
        # New: Toggle Theme Command
        tools_menu.add_command(label="Toggle Theme", command=self.toggle_theme)
        # --- Help Menu ---
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="View Help", command=self.view_help)
        help_menu.add_command(label="About", command=self.about_info)

    def setup_toolbar(self):
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(self.toolbar, text="New Notebook", command=self.new_notebook).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(self.toolbar, text="Connect", command=self.connect_runtime).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(self.toolbar, text="Add Code Cell", command=self.add_code_cell).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(self.toolbar, text="Add Markdown Cell", command=self.add_markdown_cell).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(self.toolbar, text="Run All", command=self.run_all_cells).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(self.toolbar, text="Restart Runtime", command=self.restart_runtime).pack(side=tk.LEFT, padx=2, pady=2)

    def setup_main_area(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas = tk.Canvas(self.main_frame)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        # Use a normal tk.Frame for the cell container (to allow bg changes).
        self.cells_container = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.cells_container, anchor="nw")
        self.cells_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # --- Theme Methods ---
    def toggle_theme(self):
        # Toggle the current theme.
        if self.current_theme == "light":
            self.current_theme = "dark"
        else:
            self.current_theme = "light"
        self.apply_theme()

    def apply_theme(self):
        # Define color schemes.
        # To achieve a fully "black + green" dark mode, we set everything to black for background
        # and green for the text. For light mode we keep conventional black-on-white.
        if self.current_theme == "light":
            theme = {
                "bg": "#ffffff",
                "fg": "#000000",
                "editor_bg": "#ffffff",
                "editor_fg": "#000000",
                "output_bg": "#f0f0f0",
                "menu_fg": "#000000"  # For light mode, menus use black text.
            }
        else:
            theme = {
                "bg": "#000000",
                "fg": "#00ff00",           # Green text (use "#ff0000" for red)
                "editor_bg": "#000000",
                "editor_fg": "#00ff00",      # Green text
                "output_bg": "#000000",
                "menu_fg": "#00ff00"         # Menus display green text
            }
        # Update the root window.
        self.root.configure(bg=theme["bg"])
        # Update the canvas and container.
        self.canvas.configure(bg=theme["bg"])
        self.cells_container.configure(bg=theme["bg"])
        # Update menu default options.
        self.root.option_add("*Menu.background", theme["bg"])
        self.root.option_add("*Menu.foreground", theme["menu_fg"])
        # Update styles via ttk.Style for ttk widgets.
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TFrame", background=theme["bg"])
        style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
        style.configure("TButton", background=theme["bg"], foreground=theme["fg"])
        # Update toolbar and main frame backgrounds.
        self.toolbar.configure(style="TFrame")
        self.main_frame.configure(style="TFrame")
        # Update each cell's UI.
        for cell_ui in self.cells_ui:
            try:
                cell_ui["frame"].configure(bg=theme["bg"])
            except tk.TclError:
                # If the widget does not support the bg option, ignore.
                pass
            if "text_editor" in cell_ui and cell_ui["text_editor"]:
                cell_ui["text_editor"].configure(bg=theme["editor_bg"], fg=theme["editor_fg"],
                                                   insertbackground=theme["editor_fg"])
            if cell_ui["output_area"] is not None:
                cell_ui["output_area"].configure(bg=theme["output_bg"], fg=theme["fg"])

    # --- File Menu Commands ---
    def new_notebook(self):
        for cell_ui in self.cells_ui:
            cell_ui["frame"].destroy()
        self.cells_ui.clear()
        self.engine.cells.clear()
        messagebox.showinfo("New Notebook", "New notebook created.")

    def open_notebook(self):
        filename = filedialog.askopenfilename(filetypes=[("Jupyter Notebook", "*.ipynb")])
        if filename:
            messagebox.showinfo("Open Notebook", f"Notebook '{filename}' opened (simulation).")

    def save_notebook(self):
        messagebox.showinfo("Save Notebook", "Notebook saved (simulation).")

    def save_copy(self):
        messagebox.showinfo("Save a Copy", "Notebook copy saved (simulation).")

    # --- Updated Download as .ipynb Command ---
    def download_notebook(self):
        # Ask user where to save the notebook file.
        filename = filedialog.asksaveasfilename(
            defaultextension=".ipynb",
            filetypes=[("Jupyter Notebook", "*.ipynb")],
            title="Save Notebook As",
            initialdir="~/Downloads"  # Change as desired.
        )
        if not filename:
            return  # User cancelled.
        # Build the notebook JSON structure.
        notebook_dict = {
            "cells": [],
            "metadata": {
                "language_info": {
                    "name": "python",
                    "version": "3.x"
                },
                "orig_nbformat": 4
            },
            "nbformat": 4,
            "nbformat_minor": 2
        }
        # Loop over the engine cells.
        for cell in self.engine.cells:
            if cell.get("type") == "code":
                nbcell = {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": cell.get("content", "").splitlines(keepends=True)
                }
            elif cell.get("type") == "markdown":
                nbcell = {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": cell.get("content", "").splitlines(keepends=True)
                }
            else:
                nbcell = {
                    "cell_type": "raw",
                    "metadata": {},
                    "source": cell.get("content", "").splitlines(keepends=True)
                }
            notebook_dict["cells"].append(nbcell)
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(notebook_dict, f, indent=4)
            messagebox.showinfo("Download", f"Notebook successfully saved as:\n{filename}")
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to save notebook: {e}")

    # --- Edit Menu Commands (Simulation) ---
    def undo_action(self):
        messagebox.showinfo("Undo", "Undo action (simulation).")

    def redo_action(self):
        messagebox.showinfo("Redo", "Redo action (simulation).")

    def cut_action(self):
        messagebox.showinfo("Cut", "Cut action (simulation).")

    def copy_action(self):
        messagebox.showinfo("Copy", "Copy action (simulation).")

    def paste_action(self):
        messagebox.showinfo("Paste", "Paste action (simulation).")

    # --- Insert Menu Commands ---
    def add_code_cell(self):
        cell = self.engine.add_cell(cell_type="code", content="")
        self.create_cell_ui(cell, cell_type="code")

    def add_markdown_cell(self):
        cell = self.engine.add_cell(cell_type="markdown", content="Enter markdown here...")
        self.create_cell_ui(cell, cell_type="markdown")

    def create_cell_ui(self, cell, cell_type="code"):
        cell_frame = ttk.Frame(self.cells_container, relief="solid", borderwidth=1, padding=5)
        cell_frame.pack(fill=tk.X, padx=5, pady=5)
        header = ttk.Frame(cell_frame)
        header.pack(fill=tk.X)
        cell_index = len(self.cells_ui) + 1
        ttk.Label(header, text=f"{cell_type.capitalize()} Cell {cell_index}", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        if cell_type == "code":
            run_btn = ttk.Button(header, text="Run", command=lambda: self.run_specific_cell(cell, cell_frame))
            run_btn.pack(side=tk.RIGHT, padx=2)
        if cell_type == "code":
            text_editor = tk.Text(cell_frame, height=8, wrap="word")
        else:
            text_editor = tk.Text(cell_frame, height=5, wrap="word", background="#ffffe0")
        text_editor.pack(fill=tk.X, pady=2)
        text_editor.insert("1.0", cell.get("content", ""))
        if cell_type == "code":
            ttk.Label(cell_frame, text="Output:", font=("Arial", 10, "italic")).pack(anchor="w")
            output_area = tk.Text(cell_frame, height=4, wrap="word", background="#f0f0f0")
            output_area.pack(fill=tk.X, pady=2)
            output_area.config(state=tk.DISABLED)
        else:
            output_area = None
        cell_ui = {"frame": cell_frame, "text_editor": text_editor, "output_area": output_area, "cell": cell, "type": cell_type}
        self.cells_ui.append(cell_ui)
        # Apply the current theme to the new cell.
        self.apply_theme()

    # --- Runtime Menu Commands ---
    def run_current_cell(self):
        if self.cells_ui:
            last_cell_ui = self.cells_ui[-1]
            self.run_specific_cell(last_cell_ui["cell"], last_cell_ui["frame"])
        else:
            messagebox.showwarning("Run Current Cell", "No cell available to run.")

    def run_all_cells(self):
        for cell_ui in self.cells_ui:
            if cell_ui["type"] == "code":
                self.run_specific_cell(cell_ui["cell"], cell_ui["frame"])

    def run_specific_cell(self, cell, cell_frame):
        for cell_ui in self.cells_ui:
            if cell_ui["frame"] == cell_frame:
                code = cell_ui["text_editor"].get("1.0", tk.END).strip()
                cell["content"] = code
                def execute_and_update():
                    if cell["type"] == "code":
                        self.engine.run_cell(cell)
                        output = cell.get("output", "")
                        self.root.after(0, lambda: self.update_output(cell_ui["output_area"], output))
                    else:
                        self.root.after(0, lambda: self.update_markdown(cell_ui["text_editor"]))
                threading.Thread(target=execute_and_update, daemon=True).start()
                break

    def update_output(self, output_area, output):
        output_area.config(state=tk.NORMAL)
        output_area.delete("1.0", tk.END)
        output_area.insert(tk.END, output)
        output_area.config(state=tk.DISABLED)

    def update_markdown(self, text_widget):
        # Placeholder for markdown rendering.
        pass

    def restart_runtime(self):
        for cell_ui in self.cells_ui:
            if cell_ui["type"] == "code" and cell_ui["output_area"]:
                cell_ui["output_area"].config(state=tk.NORMAL)
                cell_ui["output_area"].delete("1.0", tk.END)
                cell_ui["output_area"].config(state=tk.DISABLED)
        messagebox.showinfo("Restart Runtime", "Runtime restarted (simulation).")

    def change_runtime_type(self):
        new_type = simpledialog.askstring("Change Runtime", "Enter runtime type (e.g., Python 3, GPU, TPU):", initialvalue="Python 3")
        if new_type:
            messagebox.showinfo("Change Runtime", f"Runtime type changed to {new_type} (simulation).")

    # --- Tools Menu Commands ---
    def show_table_of_contents(self):
        toc = ""
        for index, cell_ui in enumerate(self.cells_ui, start=1):
            toc += f"Cell {index} - {cell_ui['type'].capitalize()} Cell\n"
        messagebox.showinfo("Table of Contents", toc)

    def clear_all_outputs(self):
        for cell_ui in self.cells_ui:
            if cell_ui["type"] == "code" and cell_ui["output_area"]:
                cell_ui["output_area"].config(state=tk.NORMAL)
                cell_ui["output_area"].delete("1.0", tk.END)
                cell_ui["output_area"].config(state=tk.DISABLED)
        messagebox.showinfo("Clear Outputs", "All outputs cleared.")

    # --- Help Menu Commands ---
    def view_help(self):
        help_text = (
            "This is a simulation of Google Colab functionalities using Tkinter.\n\n"
            "Features include:\n"
            " - Notebook management (new, open, save, download)\n"
            " - Code and Markdown cells\n"
            " - Execution of cells\n"
            " - Runtime management (restart, change type)\n"
            " - Basic editing functions\n"
            " - Table of contents\n"
            " - Clear outputs\n"
            " - Theme toggle (light/dark mode with menu text in green on dark mode)\n"
            " - Download notebook as a .ipynb file to a selected folder"
        )
        messagebox.showinfo("Help", help_text)

    def about_info(self):
        messagebox.showinfo("About", "Modular Notebook Application (Simulation of Google Colab)\nVersion 1.0")

    # --- Additional Toolbar Command ---
    def connect_runtime(self):
        messagebox.showinfo("Connect", "Runtime connected (simulation).")

